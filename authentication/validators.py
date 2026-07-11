from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import CommonPasswordValidator
from django.utils.translation import gettext as _
import re
import hashlib
import requests
from typing import List, Dict, Any


# ========================= Validación de imágenes (avatar / perfil) =========================

# Límites compartidos por el registro (UserProfileSerializer) y la subida de imagen de
# perfil (ProfileImageSerializer/ProfileImageView), para que ambos flujos exijan lo mismo.
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
ALLOWED_IMAGE_CONTENT_TYPES = ('image/jpeg', 'image/png', 'image/webp')


def validate_image_file(value):
    """
    Valida un archivo de imagen subido: tamaño (<=5MB) y formato (JPG/PNG/WebP).

    Reutilizable como validador de campo en serializers (registro e imagen de perfil)
    y, si se quisiera, como validador de un ImageField del modelo. Lanza
    django.core.exceptions.ValidationError, que DRF captura y traduce a un error 400
    del campo correspondiente.

    El content_type solo está disponible en archivos recién subidos (UploadedFile);
    si no lo está (p. ej. un FieldFile ya persistido), se omite esa comprobación.
    """
    if value is None:
        return value

    size = getattr(value, 'size', None)
    if size is not None and size > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError("La imagen no puede ser mayor a 5MB")

    content_type = getattr(value, 'content_type', None)
    if content_type is not None and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValidationError("Solo se permiten imágenes en formato JPG, PNG o WebP")

    return value


class CustomPasswordValidator:
    """
    Validador personalizado de contraseñas con requisitos de seguridad mejorados
    """
    
    def __init__(self, min_length=12, require_uppercase=True, require_lowercase=True, 
                 require_digits=True, require_special=True, max_similarity=0.7):
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digits = require_digits
        self.require_special = require_special
        self.max_similarity = max_similarity
    
    def validate(self, password, user=None):
        """
        Valida la contraseña según los criterios establecidos
        """
        errors = []
        
        # Verificar longitud mínima
        if len(password) < self.min_length:
            errors.append(
                _('La contraseña debe tener al menos %(min_length)d caracteres.') % 
                {'min_length': self.min_length}
            )
        
        # Verificar mayúsculas
        if self.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append(_('La contraseña debe contener al menos una letra mayúscula.'))
        
        # Verificar minúsculas
        if self.require_lowercase and not re.search(r'[a-z]', password):
            errors.append(_('La contraseña debe contener al menos una letra minúscula.'))
        
        # Verificar dígitos
        if self.require_digits and not re.search(r'\d', password):
            errors.append(_('La contraseña debe contener al menos un número.'))
        
        # Verificar caracteres especiales
        if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append(_('La contraseña debe contener al menos un carácter especial (!@#$%^&*(),.?":{}|<>).'))
        
        # Verificar patrones comunes
        if self._has_common_patterns(password):
            errors.append(_('La contraseña contiene patrones comunes que son fáciles de adivinar.'))
        
        # Verificar secuencias
        if self._has_sequences(password):
            errors.append(_('La contraseña contiene secuencias de caracteres que son fáciles de adivinar.'))
        
        # Verificar repeticiones
        if self._has_repetitions(password):
            errors.append(_('La contraseña contiene demasiadas repeticiones de caracteres.'))
        
        if errors:
            raise ValidationError(errors)
    
    def get_help_text(self):
        """
        Retorna el texto de ayuda para el usuario
        """
        return _(
            'Tu contraseña debe cumplir con los siguientes requisitos:\n'
            '• Mínimo %(min_length)d caracteres\n'
            '• Al menos una letra mayúscula\n'
            '• Al menos una letra minúscula\n'
            '• Al menos un número\n'
            '• Al menos un carácter especial (!@#$%%^&*(),.?":{}|<>)\n'
            '• No debe contener patrones comunes o secuencias'
        ) % {'min_length': self.min_length}
    
    def _has_common_patterns(self, password: str) -> bool:
        """
        Verifica si la contraseña contiene patrones comunes
        """
        common_patterns = [
            r'123', r'abc', r'qwe', r'asd', r'zxc',
            r'password', r'admin', r'user', r'login',
            r'welcome', r'hello', r'test', r'demo'
        ]
        
        password_lower = password.lower()
        for pattern in common_patterns:
            if pattern in password_lower:
                return True
        return False
    
    def _has_sequences(self, password: str) -> bool:
        """
        Verifica si la contraseña contiene secuencias de caracteres
        """
        # Secuencias de teclado
        keyboard_sequences = [
            'qwerty', 'asdfgh', 'zxcvbn',
            '123456', '654321', '789012'
        ]
        
        password_lower = password.lower()
        for seq in keyboard_sequences:
            if seq in password_lower:
                return True
        
        # Secuencias alfabéticas
        if re.search(r'abcdef|bcdefg|cdefgh|defghi|efghij', password_lower):
            return True
        
        return False
    
    def _has_repetitions(self, password: str) -> bool:
        """
        Verifica si la contraseña contiene demasiadas repeticiones
        """
        # Verificar repeticiones de 3 o más caracteres consecutivos
        for i in range(len(password) - 2):
            if password[i] == password[i+1] == password[i+2]:
                return True
        
        # Verificar si más del 30% de los caracteres son iguales
        char_counts = {}
        for char in password:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        max_count = max(char_counts.values())
        if max_count > len(password) * 0.3:
            return True
        
        return False


class BreachPasswordValidator:
    """
    Validador que verifica si la contraseña ha sido comprometida en brechas de datos
    """
    
    def __init__(self, api_url="https://api.pwnedpasswords.com/range/"):
        self.api_url = api_url
    
    def validate(self, password, user=None):
        """
        Verifica si la contraseña ha sido comprometida
        """
        try:
            # Generar hash SHA-1 de la contraseña
            password_hash = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
            prefix = password_hash[:5]
            suffix = password_hash[5:]
            
            # Consultar la API de Have I Been Pwned
            response = requests.get(f"{self.api_url}{prefix}", timeout=5)
            response.raise_for_status()
            
            # Verificar si el sufijo del hash está en la respuesta
            if suffix in response.text:
                raise ValidationError(
                    _('Esta contraseña ha sido comprometida en brechas de datos. '
                      'Por favor, elige una contraseña diferente.')
                )
                
        except requests.RequestException:
            # Si no se puede conectar a la API, continuar sin validación
            pass
    
    def get_help_text(self):
        return _(
            'Tu contraseña será verificada contra una base de datos de contraseñas comprometidas.'
        )


class UserAttributeSimilarityValidator:
    """
    Validador que verifica la similitud con atributos del usuario
    """
    
    def __init__(self, max_similarity=0.7, user_attributes=None):
        self.max_similarity = max_similarity
        self.user_attributes = user_attributes or ('username', 'first_name', 'last_name', 'email')
    
    def validate(self, password, user=None):
        if not user:
            return
        
        for attribute_name in self.user_attributes:
            value = getattr(user, attribute_name, None)
            if value and self._is_similar(password, value):
                raise ValidationError(
                    _('La contraseña es demasiado similar a tu %(attribute_name)s.') % 
                    {'attribute_name': attribute_name}
                )
    
    def _is_similar(self, password: str, value: str) -> bool:
        """
        Calcula la similitud entre la contraseña y un valor del usuario
        """
        if not value:
            return False
        
        # Convertir a minúsculas para comparación
        password_lower = password.lower()
        value_lower = value.lower()
        
        # Verificar si el valor está contenido en la contraseña o viceversa
        if value_lower in password_lower or password_lower in value_lower:
            return True
        
        # Calcular similitud usando distancia de Levenshtein simplificada
        similarity = self._calculate_similarity(password_lower, value_lower)
        return similarity > self.max_similarity
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calcula la similitud entre dos strings usando distancia de Levenshtein
        """
        if len(str1) < len(str2):
            str1, str2 = str2, str1
        
        if len(str2) == 0:
            return 0.0
        
        # Implementación simplificada de distancia de Levenshtein
        previous_row = list(range(len(str2) + 1))
        for i, c1 in enumerate(str1):
            current_row = [i + 1]
            for j, c2 in enumerate(str2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        distance = previous_row[-1]
        max_len = max(len(str1), len(str2))
        similarity = 1 - (distance / max_len)
        
        return similarity
    
    def get_help_text(self):
        return _(
            'Tu contraseña no puede ser demasiado similar a tu información personal.'
        )


class PasswordHistoryValidator:
    """
    Validador que verifica que la nueva contraseña no sea similar a las anteriores
    """
    
    def __init__(self, history_count=5):
        self.history_count = history_count
    
    def validate(self, password, user=None):
        if not user:
            return
        
        # Obtener historial de contraseñas (implementar según tu modelo)
        # Este es un ejemplo conceptual
        try:
            from .models import PasswordHistory
            recent_passwords = PasswordHistory.objects.filter(
                user=user
            ).order_by('-created_at')[:self.history_count]
            
            for old_password in recent_passwords:
                if self._is_similar(password, old_password.password_hash):
                    raise ValidationError(
                        _('La nueva contraseña no puede ser similar a una contraseña anterior.')
                    )
        except ImportError:
            # Si no existe el modelo PasswordHistory, continuar sin validación
            pass
    
    def _is_similar(self, new_password: str, old_password_hash: str) -> bool:
        """
        Verifica si la nueva contraseña es similar a una anterior
        """
        # Implementar lógica de comparación de similitud
        # Por ahora, solo verificar si son idénticas
        return hashlib.sha1(new_password.encode('utf-8')).hexdigest() == old_password_hash
    
    def get_help_text(self):
        return _(
            'Tu nueva contraseña no puede ser similar a las últimas %(count)d contraseñas utilizadas.'
        ) % {'count': self.history_count}
