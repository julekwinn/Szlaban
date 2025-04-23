import numpy as np
import matplotlib.pyplotas as plt  # Nie: import pyplot
from scipy.optimize import curve_fit  # Nie: import scipy.curve_fit

# Dane z tabeli dla NLOS
odleglosc = np.array([3, 6, 9, 12, 15, 18, 21, 24, 27, 30])
NLOS_dBm = np.array([-32, -35, -48, -54, -55, -62, -67, -72, -78, -80])

# Rysowanie wykresu logarytmicznego
plt.figure(figsize=(10, 6))
plt.scatter(odleglosc, NLOS_dBm, color='green', marker='o')
# Dodanie linii łączącej punkty pomiarowe
plt.plot(odleglosc, NLOS_dBm, 'g-', label='Zmierzone wartości')

# Model potęgowy: P(d) = P(d0) - 10*n*log10(d/d0)
# gdzie P(d) to moc w odległości d, P(d0) to moc w odległości odniesienia d0, n to wykładnik tłumienia

# Funkcja modelu potęgowego dla dopasowania
def model_potegowy(d, P_d0, n):
    d0 = 3  # Przyjmuję odległość odniesienia jako 3 metry (pierwszy punkt pomiarowy)
    return P_d0 - 10 * n * np.log10(d / d0)

# Dopasowanie parametrów modelu
popt, pcov = curve_fit(model_potegowy, odleglosc, NLOS_dBm)
P_d0_fitted, n_fitted = popt

# Generowanie wartości dla linii trendu z rozszerzonym zakresem
odleglosc_model = np.linspace(min(odleglosc) * 0.9, max(odleglosc) * 1.2, 100)
NLOS_dBm_model = model_potegowy(odleglosc_model, P_d0_fitted, n_fitted)

# Dodanie linii trendu
plt.plot(odleglosc_model, NLOS_dBm_model, 'r-', label=f'Model potęgowy: P(d) = {P_d0_fitted:.2f} - 10*{n_fitted:.2f}*log10(d/d0)')

# Ustawienia wykresu
plt.xscale('log')
# Ustawienie zakresu osi X
plt.xlim(min(odleglosc) * 0.9, max(odleglosc) * 1.2)
plt.grid(True, which="both", ls="-")
plt.xlabel('Odległość [m]')
plt.ylabel('Poziom sygnału [dBm]')
plt.title('NLOS')
plt.legend()

# Dodanie tekstu z parametrami modelu
plt.figtext(0.5, 0.03, f'Parametry modelu potęgowego:\nP(d0=3m) = {P_d0_fitted:.2f} dBm \n γ = {n_fitted:.2f}',
            ha='center', bbox={'facecolor':'white', 'alpha':0.5, 'pad':10})

# Zwiększenie dolnego marginesu
plt.tight_layout(rect=[0, 0.1, 1, 1])
plt.show()

print(f"Parametry modelu potęgowego NLOS:")
print(f"P(d0=3m) = {P_d0_fitted:.2f} dBm (moc w odległości odniesienia)")
print(f"n = {n_fitted:.2f} (wykładnik tłumienia)")

