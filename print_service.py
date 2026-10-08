import time
import json
import sys
from pathlib import Path

import requests
import win32print


# =========================================================
# CONFIG FILE LOCATION
# =========================================================

if getattr(sys, "frozen", False):

    BASE_DIR = Path(sys.executable).resolve().parent

else:

    BASE_DIR = Path(__file__).resolve().parent


CONFIG_FILE = BASE_DIR / "config.json"


# =========================================================
# LOAD CONFIG
# =========================================================

try:

    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        config = json.load(file)

except Exception as error:

    print("================================")
    print("CONFIG FILE ERROR")
    print("================================")
    print(error)
    print()
    print("config.json file check karo.")
    input("Press Enter to close...")
    sys.exit()


# =========================================================
# CONFIG VALUES
# =========================================================

RAILWAY_URL = config.get(
    "railway_url",
    ""
)

RESTAURANT_ID = str(
    config.get(
        "restaurant_id",
        ""
    )
)

PRINT_TOKEN = config.get(
    "print_token",
    ""
)

PRINTER_NAME = config.get(
    "printer_name",
    ""
)

TEST_MODE = config.get(
    "test_mode",
    False
)

POLL_SECONDS = int(
    config.get(
        "poll_seconds",
        5
    )
)


# =========================================================
# CHECK CONFIG
# =========================================================

if not RAILWAY_URL:

    print("Railway URL missing.")
    input("Press Enter to close...")
    sys.exit()


if not RESTAURANT_ID:

    print("Restaurant ID missing.")
    input("Press Enter to close...")
    sys.exit()


if not PRINT_TOKEN:

    print("Print token missing.")
    input("Press Enter to close...")
    sys.exit()


if not PRINTER_NAME:

    print("Printer name missing.")
    input("Press Enter to close...")
    sys.exit()


# =========================================================
# CHECK PRINTER
# =========================================================

def check_printer():

    try:

        printer_handle = win32print.OpenPrinter(
            PRINTER_NAME
        )

        win32print.ClosePrinter(
            printer_handle
        )

        return True

    except Exception as error:

        print()
        print("================================")
        print("PRINTER ERROR")
        print("================================")
        print(
            "Printer:",
            PRINTER_NAME
        )
        print(
            "Error:",
            error
        )

        return False


# =========================================================
# GET PENDING PRINT JOBS
# =========================================================

def get_pending_jobs():

    try:

        response = requests.get(

            f"{RAILWAY_URL}/api/print-jobs",

            params={

                "restaurant_id":
                    RESTAURANT_ID,

                "token":
                    PRINT_TOKEN

            },

            timeout=15

        )

        if response.status_code != 200:

            print(
                "API Error:",
                response.status_code,
                response.text
            )

            return []

        data = response.json()

        return data.get(
            "jobs",
            []
        )

    except Exception as error:

        print(
            "Connection error:",
            error
        )

        return []


# =========================================================
# MARK PRINT JOB AS PRINTED
# =========================================================

def mark_job_printed(
    print_job_id
):

    try:

        response = requests.post(

            f"{RAILWAY_URL}/api/print-jobs/"
            f"{print_job_id}/complete",

            params={

                "restaurant_id":
                    RESTAURANT_ID,

                "token":
                    PRINT_TOKEN

            },

            timeout=15

        )

        if response.status_code == 200:

            print(
                "Print job completed:",
                print_job_id
            )

            return True

        print(
            "Complete API error:",
            response.status_code,
            response.text
        )

        return False

    except Exception as error:

        print(
            "Complete request error:",
            error
        )

        return False


# =========================================================
# SAFE TEXT
# =========================================================

def safe_text(
    value
):

    return str(
        value
    ).encode(
        "cp437",
        errors="replace"
    )


# =========================================================
# BUILD RECEIPT
# =========================================================

def build_receipt(
    job
):

    ESC = b"\x1b"

    output = bytearray()


    # -----------------------------------------------------
    # INITIALIZE PRINTER
    # -----------------------------------------------------

    output += ESC + b"@"


    # -----------------------------------------------------
    # CENTER ALIGN
    # -----------------------------------------------------

    output += ESC + b"a" + b"\x01"


    # -----------------------------------------------------
    # RESTAURANT NAME
    # -----------------------------------------------------

    restaurant_name = str(
        job.get(
            "restaurant_name",
            ""
        )
    )


    # Bold ON

    output += ESC + b"E" + b"\x01"


    output += safe_text(
        restaurant_name
    )

    output += b"\n"


    # Bold OFF

    output += ESC + b"E" + b"\x00"


    output += b"==============================\n"


    # -----------------------------------------------------
    # LEFT ALIGN
    # -----------------------------------------------------

    output += ESC + b"a" + b"\x00"


    # -----------------------------------------------------
    # ORDER INFORMATION
    # -----------------------------------------------------

    order_number = str(
        job.get(
            "order_number",
            ""
        )
    )

    table_number = str(
        job.get(
            "table_number",
            ""
        )
    )


    created_at = job.get(
        "created_at"
    )


    date_text = ""

    time_text = ""


    if created_at:

        try:

            created_at = str(
                created_at
            )

            date_text = (
                created_at[8:10]
                + "-"
                + created_at[5:7]
                + "-"
                + created_at[0:4]
            )

            time_text = created_at[11:16]

        except Exception:

            date_text = ""

            time_text = ""


    output += safe_text(
        f"Order No : {order_number}\n"
    )

    output += safe_text(
        f"Table    : {table_number}\n"
    )

    output += safe_text(
        f"Date     : {date_text}\n"
    )

    output += safe_text(
        f"Time     : {time_text}\n"
    )


    output += b"\n"


    # -----------------------------------------------------
    # ITEMS HEADER
    # -----------------------------------------------------

    output += (
        b"------------------------------\n"
    )

    output += (
        b"ITEM                 QTY\n"
    )

    output += (
        b"------------------------------\n"
    )


    # -----------------------------------------------------
    # ITEMS
    # -----------------------------------------------------

    for item in job.get(
        "items",
        []
    ):

        item_name = str(
            item.get(
                "name",
                ""
            )
        )

        quantity = str(
            item.get(
                "quantity",
                ""
            )
        )


        # Maximum 19 characters

        if len(item_name) > 19:

            item_name = (
                item_name[:19]
            )


        line = (
            f"{item_name:<20}"
            f"{quantity:>3}\n"
        )


        output += safe_text(
            line
        )


    # -----------------------------------------------------
    # TOTAL
    # -----------------------------------------------------

    output += (
        b"------------------------------\n"
    )


    total_amount = job.get(
        "total_amount",
        0
    )


    try:

        total_text = (
            f"Rs.{float(total_amount):.0f}"
        )

    except Exception:

        total_text = (
            f"Rs.{total_amount}"
        )


    total_line = (
        f"{'TOTAL AMOUNT':<20}"
        f"{total_text:>10}\n"
    )


    output += safe_text(
        total_line
    )


    output += (
        b"==============================\n"
    )


    # -----------------------------------------------------
    # THANK YOU
    # -----------------------------------------------------

    output += ESC + b"a" + b"\x01"


    output += (
        b"THANK YOU!\n"
    )


    output += b"\n"

    output += b"\n"

    output += b"\n"


    return bytes(
        output
    )


# =========================================================
# ACTUAL PRINT
# =========================================================

def print_bill(
    job
):

    printer_handle = None

    try:

        printer_handle = win32print.OpenPrinter(
            PRINTER_NAME
        )


        document_handle = win32print.StartDocPrinter(

            printer_handle,

            1,

            (
                "Cafe QR Automatic Bill",
                None,
                "RAW"
            )

        )


        try:

            win32print.StartPagePrinter(
                printer_handle
            )


            receipt_data = build_receipt(
                job
            )


            win32print.WritePrinter(

                printer_handle,

                receipt_data

            )


            win32print.EndPagePrinter(
                printer_handle
            )


        finally:

            win32print.EndDocPrinter(
                printer_handle
            )


        return True


    except Exception as error:

        print()
        print(
            "Printer error:",
            error
        )

        return False


    finally:

        if printer_handle:

            try:

                win32print.ClosePrinter(
                    printer_handle
                )

            except Exception:

                pass


# =========================================================
# PROCESS PRINT JOBS
# =========================================================

def process_jobs():

    jobs = get_pending_jobs()


    if not jobs:

        return


    for job in jobs:

        print()
        print("==============================")
        print("       NEW PRINT JOB")
        print("==============================")


        print(
            "Restaurant :",
            job.get(
                "restaurant_name",
                ""
            )
        )


        print(
            "Order      :",
            job.get(
                "order_number",
                ""
            )
        )


        print(
            "Table      :",
            job.get(
                "table_number",
                ""
            )
        )


        print(
            "Total      :",
            job.get(
                "total_amount",
                ""
            )
        )


        print(
            "Print Job  :",
            job.get(
                "print_job_id",
                ""
            )
        )


        # -------------------------------------------------
        # TEST MODE
        # -------------------------------------------------

        if TEST_MODE:

            print(
                "TEST MODE:"
            )

            print(
                "Bill received successfully."
            )

            print(
                "No physical printing."
            )


            mark_job_printed(
                job["print_job_id"]
            )

            continue


        # -------------------------------------------------
        # ACTUAL PRINT
        # -------------------------------------------------

        success = print_bill(
            job
        )


        if success:

            print(
                "Bill printed successfully."
            )


            mark_job_printed(
                job["print_job_id"]
            )


        else:

            print(
                "Bill was NOT printed."
            )

            print(
                "Print job remains PENDING."
            )


# =========================================================
# START SERVICE
# =========================================================

if __name__ == "__main__":

    print()
    print("================================")
    print("      CAFE QR PRINT SERVICE")
    print("================================")
    print()

    print(
        "Restaurant ID :",
        RESTAURANT_ID
    )

    print(
        "Printer       :",
        PRINTER_NAME
    )

    print(
        "Test mode     :",
        TEST_MODE
    )

    print(
        "Check every   :",
        POLL_SECONDS,
        "seconds"
    )

    print()


    if not check_printer():

        print()
        print(
            "Please check printer name."
        )

        input(
            "Press Enter to close..."
        )

        sys.exit()


    print(
        "Printer       : OK"
    )

    print(
        "Print service started..."
    )

    print()


    while True:

        try:

            process_jobs()

        except Exception as error:

            print(
                "Service error:",
                error
            )


        time.sleep(
            POLL_SECONDS
        )