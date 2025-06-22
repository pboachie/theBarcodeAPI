
from fastnanoid import generate

class IDGenerator:
    @staticmethod
    def generate_id() -> str:
        return generate()
