# host_check.py
import asyncio
from pathlib import Path
from computer import Computer

async def _graceful_stop(comp):
    for name in ("stop", "shutdown", "close"):
        fn = getattr(comp, name, None)
        if fn:
            try:
                if asyncio.iscoroutinefunction(fn):
                    await fn()
                else:
                    fn()
            except Exception:
                pass
            return

async def main():
    comp = Computer(use_host_computer_server=True)  # requires: python -m computer_server (running)
    await comp.run()
    try:
        # Screenshot (handle bytes vs dict return)
        shot = await comp.interface.screenshot()
        if isinstance(shot, (bytes, bytearray)):
            png = bytes(shot)
        elif isinstance(shot, dict):
            png = shot.get("png") or shot.get("image") or shot.get("data")
            if png is None:
                raise RuntimeError(f"Unexpected screenshot dict keys: {list(shot.keys())}")
        else:
            raise RuntimeError(f"Unexpected screenshot type: {type(shot)}")

        out = Path("output"); out.mkdir(exist_ok=True)
        p = out / "screenshot.png"
        p.write_bytes(png)
        print(f"✅ Screenshot saved to: {p.resolve()}")

        size = await comp.interface.get_screen_size()
        print(f"Screen size: {size}")

        # quick input sanity (safe corner)
        await comp.interface.move_cursor(50, 50)
        await comp.interface.left_click()

    finally:
        await _graceful_stop(comp)

if __name__ == "__main__":
    asyncio.run(main())
