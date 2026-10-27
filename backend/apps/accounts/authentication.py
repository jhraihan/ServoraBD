from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class ServoraJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user.is_suspended:
            raise AuthenticationFailed("This account has been suspended.",
                                       code="user_suspended")
        return user
