import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# Dane z tabeli dla LOS
odleglosc_LOS = np.array([0.35, 0.7, 1.05, 1.4, 1.75, 2.1, 2.45, 2.8, 3.15, 3.5, 3.85, 4.2, 4.55, 4.9,
                          5.25, 5.6, 5.95, 6.3, 6.65, 7, 7.35, 7.7, 8.05, 8.4, 8.75, 9.1, 9.45, 9.8,
                          10.15, 10.5, 10.85, 11.2, 11.55, 11.9, 12.25, 12.6, 12.95, 13.3])
LOS_dBm = np.array([-43, -43, -51, -49, -48, -45, -51, -53, -57, -56, -56, -56, -52, -52, -52, -52,
                    -52, -50, -50, -63, -67, -65, -62, -55, -67, -66, -69, -71, -66, -63, -67, -67,
                    -68, -68, -68, -63, -76, -78])

# Dane z tabeli dla NLOS
odleglosc_NLOS = np.array([0.35, 0.7, 1.05, 1.4, 1.75, 2.1, 2.45, 2.8, 3.15, 3.5, 3.85, 4.2, 4.55, 4.9,
                           5.25, 5.6, 5.95, 6.3, 6.65, 7, 7.35, 7.7, 8.05, 8.4, 8.75, 9.1, 9.45, 9.8,
                           10.15, 10.5, 10.85, 11.2, 11.55, 11.9, 12.25, 12.6, 12.95, 13.3])
NLOS_dBm = np.array([-53, -51, -49, -56, -55, -63, -52, -50, -51, -53, -53, -61, -54, -65, -67, -65,
                     -70, -71, -72, -64, -70, -75, -71, -67, -68, -85, -78, -78, -74, -68, -69, -84,
                     -82, -74, -75, -78, -82, -80])

# Funkcja modelu potęgowego dla dopasowania
def model_potegowy(d, P_d0, n):
    d0 = 0.35  # Przyjmuję odległość odniesienia jako 0.35 metra (pierwszy punkt pomiarowy)
    return P_d0 - 10 * n * np.log10(d / d0)

# Dopasowanie parametrów modelu dla LOS
popt_LOS, pcov_LOS = curve_fit(model_potegowy, odleglosc_LOS, LOS_dBm)
P_d0_fitted_LOS, n_fitted_LOS = popt_LOS

# Dopasowanie parametrów modelu dla NLOS
popt_NLOS, pcov_NLOS = curve_fit(model_potegowy, odleglosc_NLOS, NLOS_dBm)
P_d0_fitted_NLOS, n_fitted_NLOS = popt_NLOS

# Generowanie wartości dla linii trendu z rozszerzonym zakresem
odleglosc_model = np.linspace(min(odleglosc_LOS) * 0.9, max(odleglosc_LOS) * 1.1, 100)
LOS_dBm_model = model_potegowy(odleglosc_model, P_d0_fitted_LOS, n_fitted_LOS)
NLOS_dBm_model = model_potegowy(odleglosc_model, P_d0_fitted_NLOS, n_fitted_NLOS)

# Tworzenie wykresu dla LOS
plt.figure(figsize=(12, 6))
plt.scatter(odleglosc_LOS, LOS_dBm, color='blue', marker='o', label='Zmierzone wartości')
plt.plot(odleglosc_LOS, LOS_dBm, 'b-', alpha=0.5)
plt.plot(odleglosc_model, LOS_dBm_model, 'r-',
         label=f'Model potęgowy: P(d) = {P_d0_fitted_LOS:.2f} - 10*{n_fitted_LOS:.2f}*log10(d/d0)')

# Ustawienia wykresu LOS
plt.xscale('log')
plt.grid(True, which="both", ls="-")
plt.xlabel('Odległość [m]')
plt.ylabel('Poziom sygnału [dBm]')
plt.title('Model propagacji sygnału LOS (Line of Sight)')
plt.legend()

# Dodanie tekstu z parametrami modelu LOS
plt.figtext(0.5, 0.01, f'Parametry modelu potęgowego LOS:\nP(d0=0.35m) = {P_d0_fitted_LOS:.2f} dBm \n γ = {n_fitted_LOS:.2f}',
            ha='center', bbox={'facecolor':'white', 'alpha':0.5, 'pad':10})

# Zwiększenie dolnego marginesu
plt.tight_layout(rect=[0, 0.1, 1, 0.95])
plt.savefig('LOS_model.png')
plt.show()

# Tworzenie wykresu dla NLOS
plt.figure(figsize=(12, 6))
plt.scatter(odleglosc_NLOS, NLOS_dBm, color='green', marker='o', label='Zmierzone wartości')
plt.plot(odleglosc_NLOS, NLOS_dBm, 'g-', alpha=0.5)
plt.plot(odleglosc_model, NLOS_dBm_model, 'r-',
         label=f'Model potęgowy: P(d) = {P_d0_fitted_NLOS:.2f} - 10*{n_fitted_NLOS:.2f}*log10(d/d0)')

# Ustawienia wykresu NLOS
plt.xscale('log')
plt.grid(True, which="both", ls="-")
plt.xlabel('Odległość [m]')
plt.ylabel('Poziom sygnału [dBm]')
plt.title('Model propagacji sygnału NLOS (Non-Line of Sight)')
plt.legend()

# Dodanie tekstu z parametrami modelu NLOS
plt.figtext(0.5, 0.01, f'Parametry modelu potęgowego NLOS:\nP(d0=0.35m) = {P_d0_fitted_NLOS:.2f} dBm \n γ = {n_fitted_NLOS:.2f}',
            ha='center', bbox={'facecolor':'white', 'alpha':0.5, 'pad':10})

# Zwiększenie dolnego marginesu
plt.tight_layout(rect=[0, 0.1, 1, 0.95])
plt.savefig('NLOS_model.png')
plt.show()

# Wyświetlenie wyników
print(f"Parametry modelu potęgowego LOS:")
print(f"P(d0=0.35m) = {P_d0_fitted_LOS:.2f} dBm (moc w odległości odniesienia)")
print(f"n = {n_fitted_LOS:.2f} (wykładnik tłumienia)")

print(f"\nParametry modelu potęgowego NLOS:")
print(f"P(d0=0.35m) = {P_d0_fitted_NLOS:.2f} dBm (moc w odległości odniesienia)")
print(f"n = {n_fitted_NLOS:.2f} (wykładnik tłumienia)")

# Porównanie parametrów obu modeli
print(f"\nRóżnica wykładników tłumienia (NLOS - LOS): {n_fitted_NLOS - n_fitted_LOS:.2f}")
