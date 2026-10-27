from rest_framework.throttling import SimpleRateThrottle

class LoginRateThrottle(SimpleRateThrottle):
    scope = "login"
    rate = "5/15min"

    num_requests = 5
    duration = 15 * 60

    def get_rate(self):
        return self.rate

    def parse_rate(self, rate):
        return self.num_requests, self.duration

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }

class AdminLoginThrottle(LoginRateThrottle):
    scope = "admin_login"
