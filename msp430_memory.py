"""Memory-access foundation for the experimental MSP430F5529 simulator.

Unmapped addresses are still backed by ordinary RAM-like storage. This is not
an implementation of the F5529 memory map or its peripheral register semantics.
"""


class Memory:
    SIZE = 1 << 20

    def __init__(self):
        self.data = bytearray(self.SIZE)
        self._regions = []
        # Native batches only touch low-memory pages with no mapped devices.
        self.mapped_low_pages = bytearray(256)

    def map_region(self, start, end, peripheral):
        """Map an inclusive address range to a device with read/write methods.

        A device receives (address, width) for reads and (address, width, value)
        for writes. Word accesses remain a single operation for register side effects.
        """
        if not 0 <= start <= end < self.SIZE:
            raise ValueError('Invalid peripheral address range')
        if any(start <= last and end >= first for first, last, _ in self._regions):
            raise ValueError('Overlapping peripheral address range')
        self._regions.append((start, end, peripheral))
        for page in range(start >> 8, min((end >> 8) + 1, 256)):
            self.mapped_low_pages[page] = 1

    def _device(self, address, width):
        if width not in (1, 2) or address < 0 or address + width > self.SIZE:
            raise IndexError('Memory access outside address space')
        for start, end, device in self._regions:
            if address <= end and address + width - 1 >= start:
                if address < start or address + width - 1 > end:
                    raise ValueError('Memory access crosses peripheral boundary')
                return device
        return None

    def read(self, address, width):
        device = self._device(address, width)
        if device is not None:
            return device.read(address, width) & ((1 << (width * 8)) - 1)
        return int.from_bytes(self.data[address:address + width], 'little')

    def write(self, address, width, value):
        device = self._device(address, width)
        value &= (1 << (width * 8)) - 1
        if device is not None:
            device.write(address, width, value)
        else:
            self.data[address:address + width] = value.to_bytes(width, 'little')

    def load(self, address, data):
        """Load firmware bytes without triggering peripheral register side effects."""
        if address < 0 or address + len(data) > self.SIZE:
            raise ValueError('ELF segment outside memory')
        self.data[address:address + len(data)] = data
