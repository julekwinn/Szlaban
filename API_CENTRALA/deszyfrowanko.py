import hmac
import hashlib
from Crypto.Cipher import AES
from Crypto.Util import Counter

# Stałe z pliku config.h
PILOT_ID = bytes([0xCA, 0xFE, 0xBA, 0xBE, 0xDE, 0xAD, 0xBE, 0xEF])
CRYPTO_AES_KEY = bytes([
    0x8F, 0x3B, 0xFB, 0x77, 0xCF, 0x6C, 0x9E, 0xCC,
    0xAD, 0x67, 0xCA, 0x1F, 0xA5, 0xD5, 0xB1, 0xB1
])
CRYPTO_HMAC_KEY = bytes([
    0xB8, 0xE6, 0x2D, 0xBA, 0x0E, 0x67, 0x65, 0x7F,
    0xED, 0x03, 0x5B, 0x63, 0x1F, 0x24, 0xD7, 0xB3,
    0x31, 0x35, 0x6C, 0x14, 0xDB, 0x05, 0x8C, 0x8A,
    0x87, 0x70, 0x3B, 0x68, 0x50, 0xFB, 0xAD, 0x0F
])
CRYPTO_IV = bytes([
    0x62, 0x69, 0xD9, 0x7F, 0xB9, 0xA4, 0x71, 0x3D,
    0xC9, 0xC9, 0xD5, 0xFF, 0x40, 0xA6, 0x54, 0xFE
])

HMAC_SIZE = 32  # SHA-256 to 32 bajty


def process_hex_data(hex_data):
    # Konwertuj string heksadecymalny na bajty
    try:
        data = bytes.fromhex(hex_data.strip())
    except ValueError:
        print("BŁĄD: Nieprawidłowy format hex!")
        return

    # 1. Rozdziel na część zaszyfrowaną i HMAC
    if len(data) < HMAC_SIZE:
        print("BŁĄD: Dane zbyt krótkie!")
        return

    encrypted_part = data[:-HMAC_SIZE]
    received_hmac = data[-HMAC_SIZE:]

    print("DANE:")
    print(f"Cały pakiet:      {data.hex()}")
    print(f"Zaszyfrowana część: {encrypted_part.hex()}")
    print(f"Odebrany HMAC:     {received_hmac.hex()}")

    # 2. Oblicz HMAC dla części zaszyfrowanej
    h = hmac.new(CRYPTO_HMAC_KEY, encrypted_part, hashlib.sha256)
    calculated_hmac = h.digest()
    print(f"Obliczony HMAC:    {calculated_hmac.hex()}")

    # 3. Porównaj HMAC
    if received_hmac == calculated_hmac:
        print("\nWERYFIKACJA HMAC: POPRAWNA")

        # 4. Deszyfruj dane
        # Utwórz licznik AES-CTR
        counter = Counter.new(128, initial_value=int.from_bytes(CRYPTO_IV, byteorder='big'))
        cipher = AES.new(CRYPTO_AES_KEY, AES.MODE_CTR, counter=counter)

        # Deszyfruj
        decrypted_data = cipher.decrypt(encrypted_part)
        print(f"\nOdszyfrowane dane: {decrypted_data.hex()}")

        # 5. Wyodrębnij ID, licznik i komendę
        if len(decrypted_data) < 16:
            print("BŁĄD: Odszyfrowane dane są zbyt krótkie!")
            return

        pilot_id = decrypted_data[:8]
        counter = decrypted_data[8:16]
        command_bytes = decrypted_data[16:]

        try:
            command = command_bytes.decode('utf-8')
        except UnicodeDecodeError:
            command = command_bytes.hex()
            print("UWAGA: Nie można zdekodować komendy jako UTF-8, wyświetlam w formacie hex")

        print("\nZAWARTOŚĆ RAMKI:")
        print(f"ID pilota: {pilot_id.hex()}")
        if pilot_id == PILOT_ID:
            print("ID pilota zgodne z oczekiwanym")
        else:
            print(f"ID pilota nie zgadza się z oczekiwanym: {PILOT_ID.hex()}")

        print(f"Licznik: {counter.hex()}")
        counter_value = int.from_bytes(counter, byteorder='big')
        print(f"Wartość licznika: {counter_value}")

        print(f"Komenda: {command}")

        if "eszp_open" in command:
            print("\n>>> WYKRYTO KOMENDĘ OTWIERANIA! <<<")
    else:
        print("\nWERYFIKACJA HMAC: NIEPOPRAWNA - Możliwa manipulacja danymi!")


# Główna funkcja
def main():
    print("=== DEKODER BEZPIECZNYCH RAMEK ===")
    print("Podaj dane w formacie heksadecymalnym:")

    process_hex_data("b9282ba26be9fad9c4ddac9cb636e615d8c856540e4a9d3cfea387dcd7165ae17778eee9ee2f7b0a3df593947ed361a6bf62484c9409811849")


if __name__ == "__main__":
    main()