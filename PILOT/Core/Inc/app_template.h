/* * app_template.h
 * */

#ifndef INC_APP_TEMPLATE_H_
#define INC_APP_TEMPLATE_H_

#include <stdbool.h> // Dodaj, jeśli nie ma

void app_main(void);

// Dodaj deklarację nowej funkcji
/**
 * @brief Sends a single radio message and waits for completion or timeout.
 * * @param message The null-terminated string to send.
 * @return true if transmission was successful (TxDone), false otherwise (Timeout).
 */
bool send_single_message(const char* message);


void rx_loop(void);
void tx_loop(void);


#endif /* INC_APP_TEMPLATE_H_ */
