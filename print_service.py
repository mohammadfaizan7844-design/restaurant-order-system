import win32print
import time


def show_printers():

    print("\n==============================")
    print("AVAILABLE WINDOWS PRINTERS")
    print("==============================\n")

    printers = win32print.EnumPrinters(
        win32print.PRINTER_ENUM_LOCAL
        | win32print.PRINTER_ENUM_CONNECTIONS
    )

    if not printers:
        print("No printer found.")
        return

    for index, printer in enumerate(printers, start=1):

        printer_name = printer[2]

        print(
            f"{index}. {printer_name}"
        )


def get_default_printer():

    try:

        printer_name = win32print.GetDefaultPrinter()

        print("\nDefault printer:")
        print(printer_name)

        return printer_name

    except Exception as error:

        print(
            "\nCould not detect default printer:"
        )

        print(error)

        return None


if __name__ == "__main__":

    print("================================")
    print("CAFE QR PRINT SERVICE")
    print("================================")

    show_printers()

    get_default_printer()

    print("\nPrint service is running...")

    while True:

        time.sleep(10)