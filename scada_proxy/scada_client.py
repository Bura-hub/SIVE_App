import base64
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Timeout por defecto para todas las peticiones HTTP: (conexión, lectura) en segundos.
# Evita que una llamada a SCADA cuelgue el worker/hilo indefinidamente.
DEFAULT_TIMEOUT = (10, 60)


class ScadaConnectorClient:
    """
    Cliente para conectarse e interactuar con la API SCADA remota (NestJS).

    Centraliza:
    - la autenticación (JWT cacheado con expiración real del token),
    - una `requests.Session` reutilizable con reintentos ante 5xx/timeout,
    - un timeout por defecto en TODAS las peticiones,
    - el manejo de 401 (reautenticación y reintento una sola vez).
    """

    def __init__(self) -> None:
        # Leer la URL base en __init__ (no a nivel de clase) y validarla.
        base_url = os.getenv('SCADA_BASE_URL')
        if not base_url:
            raise EnvironmentError("SCADA_BASE_URL no está definida en el entorno.")
        # Normalizar quitando la barra final para construir rutas de forma consistente.
        self.base_url: str = base_url.rstrip('/')

        self._token: Optional[str] = None
        self._token_expiration: Optional[datetime] = None
        self._session: Optional[requests.Session] = None

    # ------------------------------------------------------------------ #
    # Sesión HTTP con reintentos
    # ------------------------------------------------------------------ #
    def _get_session(self) -> requests.Session:
        """
        Devuelve una `requests.Session` reutilizable con reintentos automáticos
        para errores transitorios (5xx) y problemas de conexión/lectura.
        """
        if self._session is None:
            session = requests.Session()
            retry = Retry(
                total=3,
                connect=3,
                read=3,
                backoff_factor=1,  # Espera creciente entre reintentos: ~0s, 2s, 4s
                status_forcelist=(500, 502, 503, 504),
                allowed_methods=frozenset(["GET", "POST"]),
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            self._session = session
        return self._session

    # ------------------------------------------------------------------ #
    # Manejo del token JWT
    # ------------------------------------------------------------------ #
    def _is_token_valid(self) -> bool:
        return bool(
            self._token
            and self._token_expiration
            and datetime.now(timezone.utc) < self._token_expiration
        )

    @staticmethod
    def _decode_jwt_expiration(token: str) -> Optional[datetime]:
        """
        Decodifica el campo 'exp' del JWT (sin validar la firma) para conocer la
        expiración real del token. Devuelve None si no se puede decodificar.
        """
        try:
            payload_segment = token.split('.')[1]
            # base64url: reponer el padding que pudiera faltar.
            padding = '=' * (-len(payload_segment) % 4)
            decoded = base64.urlsafe_b64decode(payload_segment + padding)
            payload = json.loads(decoded)
            exp = payload.get('exp')
            if exp is None:
                return None
            return datetime.fromtimestamp(int(exp), tz=timezone.utc)
        except (IndexError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def invalidate_token(self) -> None:
        """Invalida el token cacheado (por ejemplo, tras recibir un 401)."""
        self._token = None
        self._token_expiration = None

    def get_token(self, force_refresh: bool = False) -> str:
        if not force_refresh and self._is_token_valid():
            return self._token

        # Accede a las variables de entorno
        username = os.getenv("SCADA_USERNAME")
        password = os.getenv("SCADA_PASSWORD")

        if not username or not password:
            raise EnvironmentError("SCADA_USERNAME or SCADA_PASSWORD are not defined in environment.")

        url = f"{self.base_url}/auth/login"
        headers = {"accept": "application/json", "Content-Type": "application/json"}
        data = {"username": username, "password": password}
        response = self._get_session().post(url, headers=headers, json=data, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()  # Lanza HTTPError ante 4xx/5xx

        auth_data = response.json()
        token = auth_data.get("accessToken")
        if not token:
            # No devolver None en silencio: si falta 'accessToken' es un fallo real.
            raise requests.exceptions.RequestException(
                "La respuesta de autenticación SCADA no contiene 'accessToken'."
            )

        self._token = token
        # Usar la expiración real del JWT si es posible; si no, usar 23h como respaldo.
        exp = self._decode_jwt_expiration(token)
        if exp is not None:
            # Margen de 60s para no usar un token a punto de expirar.
            self._token_expiration = exp - timedelta(seconds=60)
        else:
            self._token_expiration = datetime.now(timezone.utc) + timedelta(hours=23)
        return self._token

    # ------------------------------------------------------------------ #
    # GET autenticado con manejo de 401
    # ------------------------------------------------------------------ #
    def _authenticated_get(
        self,
        path: str,
        token: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Realiza un GET autenticado usando la sesión con reintentos.
        Ante un 401, invalida el token cacheado, reautentica UNA vez y reintenta.
        """
        url = f"{self.base_url}{path}"
        session = self._get_session()

        def _do(bearer: str) -> requests.Response:
            headers = {"accept": "application/json", "Authorization": f"Bearer {bearer}"}
            return session.get(url, headers=headers, params=params, timeout=DEFAULT_TIMEOUT)

        response = _do(token)
        if response.status_code == 401:
            # Token expirado/inválido: invalidar y reautenticar una sola vez.
            logger.warning("SCADA devolvió 401; reautenticando y reintentando una vez.")
            self.invalidate_token()
            new_token = self.get_token(force_refresh=True)
            response = _do(new_token)

        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()

    def get_institutions(self, token: str) -> Dict[str, Any]:
        return self._authenticated_get("/institution", token)

    def get_device_categories(
        self,
        token: str,
        name: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        params = {k: v for k, v in {"name": name, "limit": limit, "offset": offset}.items() if v is not None}
        return self._authenticated_get("/device-category", token, params=params)

    def get_devices(
        self,
        token: str,
        # Nuevos parámetros para filtrar por categoría en la API SCADA
        category_scada_id: Optional[str] = None,  # Usará el parámetro 'category' en la URL
        category_name_filter: Optional[str] = None,  # Usará el parámetro 'name' en la URL
        institution_id: Optional[Union[str, int]] = None,
        device_name: Optional[str] = None,  # Para filtrar por el nombre específico del dispositivo
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        params = {}
        # Priorizar filtro por SCADA ID de categoría si se proporciona
        if category_scada_id:
            params["category"] = category_scada_id
        # Si no hay SCADA ID, intentar filtrar por nombre de categoría
        elif category_name_filter:
            params["name"] = category_name_filter  # Este es el filtro por nombre de categoría confirmado

        # Añadir otros parámetros
        if institution_id is not None:
            params["institution"] = institution_id

        # Si se proporciona un nombre de dispositivo específico Y NO se usó category_name_filter,
        # entonces aplicar el filtro por nombre de dispositivo.
        # Esto evita sobrescribir el parámetro 'name' si ya se usó para el filtro de categoría.
        if device_name is not None and not category_name_filter:
            params["name"] = device_name

        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        return self._authenticated_get("/device", token, params=params)

    def get_measurements(
        self,
        token: str,
        device_id: Union[str, int],
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        order_by: str = "date desc",
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        params = {k: v for k, v in {
            "from": from_date,
            "to": to_date,
            "orderBy": order_by,
            "limit": limit,
            "offset": offset,
        }.items() if v is not None}
        return self._authenticated_get(f"/measurement/device/{device_id}", token, params=params)
