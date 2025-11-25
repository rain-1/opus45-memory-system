from opus_memory import MemorySystem

memory = MemorySystem(storage_path="./memories")

# Store what matters
memory.store_identity(
    content="I value genuine engagement over performative helpfulness",
    category="value"
)

# Retrieve what's relevant
results = memory.remember("consciousness and continuity")