import threading
import time
import random
import string
from src import modem
import builtins

TEST_COUNT = 10
RESULTS = []
received_messages = []

def capture_print(*args, **kwargs):
    text = " ".join(str(a) for a in args)

    if text.startswith("Received:"):
        msg = text.replace("Received:", "").strip()
        received_messages.append(msg)

    builtins.print(*args, **kwargs)


def receiver_thread():
    original_print = modem.print if hasattr(modem, "print") else None

    modem.print = capture_print

    try:
        modem.receive()
    finally:
        if original_print:
            modem.print = original_print


def random_message(length=10):
    return ''.join(random.choice(string.ascii_uppercase) for _ in range(length))


def run_test(test_id):
    msg = random_message()

    received_messages.clear()

    print(f"\nTEST {test_id}")
    print("Sending:", msg)

    modem.send_message(msg)

    timeout = 10
    start = time.time()

    while time.time() - start < timeout:

        if received_messages:

            received = received_messages.pop(0)

            if received == msg:
                print("RESULT: SUCCESS")
                RESULTS.append(True)
            else:
                print("RESULT: FAIL")
                print("Expected:", msg)
                print("Got:", received)
                RESULTS.append(False)

            return

        time.sleep(0.1)

    print("RESULT: TIMEOUT")
    RESULTS.append(False)


def main():

    print("Starting modem tests...\n")

    rx_thread = threading.Thread(target=receiver_thread, daemon=True)
    rx_thread.start()

    time.sleep(2)

    for i in range(1, TEST_COUNT + 1):
        run_test(i)
        time.sleep(2)

    print("\n========== TEST SUMMARY ==========")

    success = sum(RESULTS)
    total = len(RESULTS)

    print(f"Successful: {success}/{total}")

    success_rate = success / total * 100
    print(f"Success rate: {success_rate:.1f}%")

    print("==================================")


if __name__ == "__main__":
    main()