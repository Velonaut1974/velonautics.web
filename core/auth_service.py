from datetime import datetime, timezone

class AuthService:
    def __init__(self):
        # Zentrale PIN-Verwaltung
        self._pins = {
            "LOGIN": "1234",
            "COMMIT": "1234",
            "ATTESTATION": "1920",
            "SUPER_SEAL": "9999"
        }
        
        # NEU: Die Authority Registry (Key-Mapping)
        # Hier werden später die echten Public Keys deiner Rollen eingetragen
        self._authority_keys = {
            "OWNER": "HIER_DEIN_OWNER_PUBLIC_KEY",
            "AUDITOR": "HIER_DEIN_AUDITOR_PUBLIC_KEY"
        }

    def validate_login(self, input_pin):
        return input_pin == self._pins["LOGIN"]

    def get_commit_context(self, input_pin, role, user):
        """
        Erzeugt ein Auth-Objekt für den CommitGuard (UI-unabhängig).
        """
        is_valid = input_pin == self._pins["COMMIT"]
        return {
            "authorized": is_valid,
            "role": role,
            "user": user,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def validate_attestation(self, input_pin):
        """
        Prüft die PIN für regulatorische Snapshots/Attestierungen.
        """
        return input_pin == self._pins["ATTESTATION"]