import json
import zlib
import base64
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

class LicenseError(Exception):
    """Zwykły błąd odczytu/weryfikacji licencji"""
    pass

class LicenseExpiredError(LicenseError):
    """Licencja wygasła (minął termin ważności)"""
    pass

class LicenseNotActiveError(LicenseError):
    """Licencja nie jest jeszcze aktywna"""
    pass

class LicenseInvalidSignatureError(LicenseError):
    """Błędny lub zmodyfikowany podpis - Próba fałszerstwa"""
    pass

class LicenseFormatError(LicenseError):
    """Nierozpoznany format (brak wymaganych pół, brak podziału kropką itp.)"""
    pass

def _add_b64_padding(b64_string: str) -> str:
    """Uzupełnia pominięty na końcu stringu kodowania Base64Url padding (=)"""
    padding = (4 - len(b64_string) % 4) % 4
    return b64_string + ("=" * padding)

def verify_and_decode(license_key: str, public_pem_bytes: bytes) -> dict:
    """
    Sprawdza podpis Ed25519 klucza na podstawie publicznego klucza, 
    dekoduje Base64Url i dekompresuje zlib z JSON,
    sprawdza daty issued oraz expires na licencji.
    Zwraca odzyskany w pełni niezmieniony obiekt dict.
    """
    if "." not in license_key:
        raise LicenseFormatError("Zły format elementu (brak kropki rozdzielającej podpis i payload).")
        
    payload_b64, signature_b64 = license_key.split(".", 1)
    
    # 1. Dekodowanie Base64
    try:
        # Pamiętamy o dodaniu wyrzuconych uprzednio znaków '=' (wyrównanie matematyczne do bloków algorytmu b64)
        payload_compressed = base64.urlsafe_b64decode(_add_b64_padding(payload_b64))
        signature = base64.urlsafe_b64decode(_add_b64_padding(signature_b64))
    except Exception as e:
        raise LicenseFormatError("Błąd dekodowania zabezpieczeń Base64Url.") from e

    # 2. Wczytanie klucza publicznego
    try:
        public_key = serialization.load_pem_public_key(public_pem_bytes)
    except Exception as e:
        raise LicenseError("We wczesnym odczycie systemu zabezpieczeń wystąpił nienormalny błąd.") from e

    # 3. Bardzo solidna weryfikacja oryginalnego podpisu Ed25519 paczki Payload
    try:
        # verify() nic nie zwróci z wyjątkiem błędnego podpisu: InvalidSignature
        public_key.verify(signature, payload_compressed)
    except InvalidSignature:
        raise LicenseInvalidSignatureError("Podpis licencji nieweryfikowalny (klucz mógł zostać naruszony manualnie).")

    # 4. Dekompresja i zlokalizowanie danych o licencji wewnątrz zabezpieczonego archiwum
    try:
        payload_json = zlib.decompress(payload_compressed).decode('utf-8')
        payload = json.loads(payload_json)
    except Exception as e:
        raise LicenseError("Mechanizmy weryfikacyjne ukończone sukcesem, ale dane pod licencji są uszkodzone.") from e

    # 5. Sprawdzenie rygorów dat w licencji
    today = datetime.now().date()
    
    try:
        issued_date = datetime.strptime(payload["issued"], "%Y-%m-%d").date()
        expires_date = datetime.strptime(payload["expires"], "%Y-%m-%d").date()
    except KeyError as e:
        raise LicenseFormatError(f"Licencji brakuje autentycznych wpisów chronologicznych: {e}")
    except ValueError:
        raise LicenseFormatError("Niekompatybilny rodzaj zapisanej daty chronologicznej YYYY-MM-DD")

    if today < issued_date:
        raise LicenseNotActiveError(f"Licencja wejdzie w aktywny obieg od nowa dopiero na dzień: {issued_date}.")
        
    if today > expires_date:
        raise LicenseExpiredError(f"Licencji upłynął termin autoryzacji z dniem: {expires_date}.")

    # Po zakończeniu pozytywnie zweryfikowanego algorytmu wypisz zawarte informacje
    return payload

if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Weryfikator kluczy licencyjnych z użyciem Ed25519")
    parser.add_argument("--license", required=True, help="Wygenerowany klucz licencyjny do weryfikacji")
    parser.add_argument("--pubkey", default="license_public.pem", help="Ścieżka do klucza publicznego")
    
    args = parser.parse_args()
    
    try:
        with open(args.pubkey, "rb") as f:
            public_pem = f.read()
    except FileNotFoundError:
        print(f"BŁĄD: Nie znaleziono klucza publicznego w formacie PEM ({args.pubkey})")
        sys.exit(1)
        
    try:
        license_data = verify_and_decode(args.license, public_pem)
        print("✅ Licencja jest WAŻNA i ZWERYFIKOWANA pomyślnie!")
        print(f"Zdekodowane dane wpisane do licencji:\n{json.dumps(license_data, indent=2, ensure_ascii=False)}")
    except LicenseError as e:
        print(f"❌ BŁĄD WERYFIKACJI LICENCJI: {e}")
        sys.exit(1)
