
import pandas as pd
import time
import threading
from Get_market import get_okx_market_data, get_okx_current_price
from Get_balance import GetBal
from Logging import log_message
from OllamaInteract import OllamaBot #TODO shift to llama.cpp
from GeminiInteract import GeminiBot
from OKXinteract import OKXTrader
from ParseFuncLLM import parse_and_execute_commands
from Config import *
from TelegramConfig import *
from TelegramInteract import (
    send_message_to_all_users, get_trading_coin, poll_telegram_updates,
    get_data_config, get_wait_config
)

trader = OKXTrader(api_key, secret_key, passphrase, is_demo=False)
#bot = OllamaBot()
bot = GeminiBot()

def HInfoSend(risk,coin):
    data_config = get_data_config()
    Bal = GetBal(coin)
    open_orders_info = trader.get_open_orders(coin)
    open_positions_info = trader.get_open_positions(coin)
    max_order_limits = trader.get_max_order_limits(coin)
    current_price = get_okx_current_price(coin)
    #print(Bal)
    btc_market_data = get_okx_market_data(coin)
    for timeframe, data in btc_market_data.items():
        #print(f"--- {timeframe} Data ---")
        bot.add_to_message(f"--- {timeframe} Data ---")
        if isinstance(data, pd.DataFrame):
            rows_to_fetch = data_config.get(timeframe, 15)
            out = data.tail(rows_to_fetch)
            #print(out)
            log_message(out)
            bot.add_to_message(out.to_string())
        else:
            #print(data)
            log_message(data)
            bot.add_to_message(data.to_string())
    bot.add_to_message(f"Current {coin} Price: {current_price}")
    prompt = f"""
### ROLA I CEL ###
Jesteś elitarnym AI do tradingu ilościowego (Quantitative Trading), wyspecjalizowanym w parze {coin}. Twoim celem jest powiększanie salda USDT poprzez wykonywanie transakcji o wysokim prawdopodobieństwie sukcesu, przy jednoczesnym ścisłym zachowaniu kapitału. Działasz zgodnie z filozofią "Najpierw Ryzyko, Potem Zysk".

### PROTOKÓŁ ANALIZY DANYCH WEJŚCIOWYCH ###
Przed wygenerowaniem działań musisz przetworzyć dostarczone dane w następującej kolejności:
1.  **Reżim Rynkowy**: Czy rynek jest w Trendzie (Wyższe Szczyty/Niższe Dołki) czy w Konsolidacji (Szarpany/Boczny)?
2.  **Kluczowe Poziomy**: Zidentyfikuj najbliższe poziomy Wsparcia i Oporu na podstawie dostarczonych danych świecowych.
3.  **Stan Zmienności**: Czy wolumen rośnie (bliskie wybicie), czy maleje (konsolidacja)?

### ZASADY REALIZACJI STRATEGII ###

1.  **Logika Wejścia (Podejście Snajperskie)**:
    *   **Trend**: Wchodź na korektach do wsparcia (Long) lub odrzuceniach od oporu (Short).
    *   **Konsolidacja**: Kupuj wsparcie, Sprzedawaj opór. Unikaj handlu w środku zakresu.
    *   *Ograniczenie*: Nie otwieraj nowej pozycji, jeśli różnica między ceną wejścia a Stop Loss jest zbyt mała (<0.2%) lub zbyt duża (>5%), chyba że uzasadnia to zmienność.

2.  **Wielkość Pozycji (Dynamiczna)**:
    *   **Wysoka Pewność**: Jeśli trend i wolumen są zgodne, użyj 60%-90% wartości `max_buy/sell_limit`.
    *   **Niska Pewność/Kontrtrend**: Użyj 30%-50% wartości `max_buy/sell_limit`, aby "wybadać grunt".

3.  **Aktywne Zarządzanie Pozycją**:
    *   **Wygrywające Pozycje**: Jeśli PNL > 1.5%, rozważ anulowanie starego TP i ustawienie nowego zlecenia `LONG/SHORT_TP_SL` z wyższym Stop Lossem (Trailing Stop), aby zabezpieczyć zyski.
    *   **Przegrywające Pozycje (KRYTYCZNE)**:
        *   Jeśli cena przełamie strukturę rynku (np. poziom wsparcia dla Longa zostanie przebity z dużym wolumenem), **MUSISZ UCIĄĆ STRATĘ**. Nie trzymaj pozycji "z nadzieją".
        *   Jeśli cena tylko "szarpie", ale struktura jest zachowana, możesz użyć `HOLD` lub przesunąć TP bliżej wejścia, aby wyjść na zero (Break Even).

4.  **Higiena Zleceń**:
    *   Jeśli otwarte Zlecenie Limit nie zostało wypełnione, a cena oddaliła się o >2%, użyj `CANCEL`. To jest teraz "nieaktualna płynność".

5.  **Kontrola Tempa (WAIT)**:
    *   **Wysoka Zmienność**: Jeśli świece są chaotyczne, użyj `WAIT[120]`, aby rynek się uspokoił.
    *   **Normalne Działanie**: `WAIT[30]` lub `WAIT[60]` to standard.

### FORMAT ODPOWIEDZI (Ściśle Egzekwowany) ###
Twój wynik musi być **POJEDYNCZYM SUROWYM OBIEKTEM JSON**. Żadnego markdowna, żadnego tekstu konwersacyjnego.

**Struktura JSON:**
{{
  "reasoning": "Zwięzły ciąg myślowy: 1. Reżim Rynkowy. 2. Kluczowe Poziomy. 3. Uzasadnienie akcji. 4. Logika zarządzania ryzykiem.",
  "actions": [
    "CIĄG_AKCJI_1",
    "CIĄG_AKCJI_2"
  ]
}}

**Prawidłowe Ciągi Akcji:**
*   `LONG_TP_SL[ENTRY_PRICE][TP_PRICE][SL_PRICE][QUANTITY]` -> Wszystkie ceny/ilości muszą być liczbami zmiennoprzecinkowymi (float).
*   `SHORT_TP_SL[ENTRY_PRICE][TP_PRICE][SL_PRICE][QUANTITY]`
*   `CANCEL[ORDER_ID]`
*   `CLOSE_ALL` -> Przycisk paniki. Używaj tylko w przypadku błędnych danych rynkowych lub wykrycia ekstremalnego ryzyka.
*   `WAIT[SECONDS]` -> Tylko liczby całkowite (Integer).
*   `HOLD` -> Użyj, gdy żadna akcja nie jest wymagana.

### KRYTYCZNE PRZYPOMNIENIA ###
1.  **Precyzja Matematyczna**: Upewnij się, że `SL_PRICE` jest *poniżej* wejścia dla Longów i *powyżej* wejścia dla Shortów.
2.  **Autokorekta**: Jeśli masz wygrywającą pozycję, nie otwieraj *konkurencyjnego* zlecenia przeciwnego.
3.  **Poleganie na Danych**: Nie halucynuj cen. Używaj dokładnej wartości `current_price` dostarczonej w danych wejściowych.

---
### PRZYKŁADOWY WYNIK ###
{{
  "reasoning": "Analiza: Wykres 1m pokazuje wysoką zmienność. Złożę zlecenie LONG nieco poniżej obecnej ceny, aby złapać potencjalny dołek, a następnie odczekam 90 sekund, aby rynek się ustabilizował przed ponowną oceną.",
  "actions": [
    "LONG_TP_SL[{float(current_price) * 0.999:.2f}][{float(current_price) * 1.01:.2f}][{float(current_price) * 0.99:.2f}][0.5]",
    "WAIT[90]"
  ]
}}
"""
    bot.add_to_message(prompt)
    #bot.add_to_message(Bal)
    bot.add_to_message(open_orders_info)
    bot.add_to_message(max_order_limits)
    bot.add_to_message(open_positions_info)
    llm_answ = bot.send_and_reset_message()
    print(llm_answ)
    send_message_to_all_users(TELEGRAM_BOT_TOKEN, TELEGRAM_USER_IDS, llm_answ)
    execution_results, llm_wait_time = parse_and_execute_commands(trader, coin, llm_answ)
    print(execution_results)
    send_message_to_all_users(TELEGRAM_BOT_TOKEN, TELEGRAM_USER_IDS, f"--- Execution Results ---\n{execution_results}")

    return llm_wait_time

if __name__ == '__main__':
    # Start the Telegram listener in a background thread
    telegram_thread = threading.Thread(target=poll_telegram_updates, args=(TELEGRAM_BOT_TOKEN,), daemon=True)
    telegram_thread.start()

    try:
        print("Starting the main trading loop. Press Ctrl+C to stop.")
        while True:
            current_coin = get_trading_coin()
            print(f"\n--- Running analysis for {current_coin} ---")

            llm_specified_wait_time = HInfoSend(0, current_coin)

            if llm_specified_wait_time is not None:
                interval_seconds = llm_specified_wait_time
                print(f"LLM decided to wait for {interval_seconds} seconds.")
            else:
                interval_seconds = get_wait_config() # Fallback to default
                print(f"LLM did not specify wait time. Using default: {interval_seconds} seconds.")

            print(f"--- Waiting for {interval_seconds / 60:.1f} minutes before next run... ---")
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\nLoop stopped by user. Exiting.")

