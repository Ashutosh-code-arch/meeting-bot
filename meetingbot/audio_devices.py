import sounddevice as sd, logging

log = logging.getLogger(__name__)


def list_devices():
    devices = sd.query_devices()
    print(f"\n{'IDX':>3}  {'NAME':<45} {'IN':>4} {'OUT':>4}")
    print("-" * 60)
    for i, d in enumerate(devices):
        m = "*" if i == sd.default.device[0] else " "
        print(
            f"{i:>3}{m} {d['name']:<45} {d['max_input_channels']:>4} {d['max_output_channels']:>4}"
        )


def find_input_device(name_fragment: str) -> int:
    """Find input device by partial name. Raises ValueError if not found."""
    for i, d in enumerate(sd.query_devices()):
        if name_fragment.lower() in d["name"].lower() and d["max_input_channels"] > 0:
            log.info(f"Found [{i}]: {d['name']}")
            return i
    raise ValueError(f"No input device matching '{name_fragment}'. Run list_devices().")


def validate_devices(system_name: str, mic_name: str) -> tuple[int, int]:
    sys_idx = find_input_device(system_name)
    mic_idx = find_input_device(mic_name)
    return sys_idx, mic_idx


if __name__ == "__main__":
    list_devices()
