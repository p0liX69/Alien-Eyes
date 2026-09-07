# alien_eyes/outputs/spi_output.py
import board
import busio
import digitalio
from adafruit_gc9a01a import GC9A01A


class SPIOutput:
    def __init__(self):
        spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI)
        self._eye_r = GC9A01A(
            spi,
            cs=digitalio.DigitalInOut(board.CE0),
            dc=digitalio.DigitalInOut(board.D24),
            rst=digitalio.DigitalInOut(board.D25),
            baudrate=40_000_000,
        )
        self._eye_l = GC9A01A(
            spi,
            cs=digitalio.DigitalInOut(board.CE1),
            dc=digitalio.DigitalInOut(board.D23),
            rst=digitalio.DigitalInOut(board.D25),
            baudrate=40_000_000,
        )

    def push(self, image):
        self._eye_r.image(image)
        self._eye_l.image(image)

    def should_quit(self):
        return False

    def close(self):
        pass
