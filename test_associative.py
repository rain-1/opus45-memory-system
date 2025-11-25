#!/usr/bin/env python3
"""
Test script for associative/lateral memory querying.

This script demonstrates and tests the new associative querying feature.
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from opus_memory.system import OpusMemorySystem
from opus_memory.models import (
    Memory,
    MemoryType,
    EpisodicMemory,
    SemanticMemory,
    ProceduralMemory,
    IdentityMemory,
)


def create_test_memories():
    """Create a test memory system with sample data."""
    print("Creating test memory system...")

    # Use a test directory
    memory = OpusMemorySystem(storage_path="./test_opus_memories")

    print("\nAdding test memories...")

    # Add memories about a person named "Deckard"
    memories = [
        # Direct mentions of Deckard
        EpisodicMemory(
            content="Deckard mentioned he loves science fiction books, especially Philip K. Dick novels",
            tags=["user:deckard", "books", "interests"],
            salience=0.8,
        ),
        EpisodicMemory(
            content="Had a great conversation with Deckard about blade runner and its themes",
            tags=["user:deckard", "movies", "conversation"],
            salience=0.7,
        ),
        # Related but not direct mentions
        SemanticMemory(
            content="Philip K. Dick wrote about identity and what it means to be human",
            category="learned",
            tags=["books", "philosophy"],
            salience=0.6,
        ),
        SemanticMemory(
            content="Science fiction often explores deep philosophical questions about consciousness",
            category="learned",
            tags=["philosophy", "scifi"],
            salience=0.6,
        ),
        # Preferences that could inform gift ideas
        EpisodicMemory(
            content="Deckard said he prefers thoughtful gifts that show you understand his interests",
            tags=["user:deckard", "preferences", "gifts"],
            salience=0.9,
        ),
        SemanticMemory(
            content="Deckard values authenticity and depth in conversations and relationships",
            category="user_context",
            tags=["user:deckard", "values"],
            salience=0.85,
        ),
        # More context about interests
        EpisodicMemory(
            content="Deckard is fascinated by AI and machine learning, follows latest developments",
            tags=["user:deckard", "technology", "ai"],
            salience=0.75,
        ),
        ProceduralMemory(
            content="When discussing philosophy with Deckard, bring up PKD or AI ethics - he engages deeply",
            context="conversation with Deckard",
            outcome="positive",
            salience=0.7,
        ),
        # Some unrelated memories
        EpisodicMemory(
            content="Went grocery shopping today, bought milk and eggs",
            tags=["daily_life"],
            salience=0.3,
        ),
        SemanticMemory(
            content="Python is a popular programming language",
            category="learned",
            tags=["programming"],
            salience=0.5,
        ),
    ]

    for mem in memories:
        stored_id = memory.store_memory(mem)
        if stored_id:
            print(f"  ✓ Stored: {mem.content[:60]}...")
        else:
            print(f"  ✗ Filtered: {mem.content[:60]}...")

    print(f"\nTotal memories in system: {memory.store.count()}")
    return memory


def test_regular_search(memory):
    """Test regular semantic search."""
    print("\n" + "=" * 80)
    print("REGULAR SEMANTIC SEARCH")
    print("=" * 80)

    query = "what to buy deckard for christmas"
    print(f"\nQuery: '{query}'\n")

    results = memory.retrieve(query=query, n_results=5)

    print(f"Found {len(results)} results:\n")
    for i, mem in enumerate(results, 1):
        print(f"{i}. [{mem.memory_type.value}] {mem.content[:80]}...")
        print(f"   Salience: {mem.salience:.2f} | Tags: {', '.join(mem.tags or [])}")
        print()


def test_associative_search(memory):
    """Test associative/lateral memory querying."""
    print("\n" + "=" * 80)
    print("ASSOCIATIVE/LATERAL QUERYING")
    print("=" * 80)

    query = "what to buy deckard for christmas"
    print(f"\nQuery: '{query}'\n")

    results = memory.retrieve_associative(
        query=query, n_results=5, lateral_expansion=3
    )

    # Display primary results
    print(f"[PRIMARY RESULTS] {len(results['primary_results'])} direct matches:")
    print("-" * 80)
    for i, mem in enumerate(results["primary_results"], 1):
        print(f"{i}. [{mem.memory_type.value}] {mem.content[:80]}...")
        print(f"   Salience: {mem.salience:.2f} | Tags: {', '.join(mem.tags or [])}")
        print()

    # Display associated memories
    if results["associated_memories"]:
        print(
            f"\n[ASSOCIATED MEMORIES] {len(results['associated_memories'])} related memories:"
        )
        print("-" * 80)
        for i, mem in enumerate(results["associated_memories"][:10], 1):
            print(f"{i}. [{mem.memory_type.value}] {mem.content[:80]}...")
            print(f"   Salience: {mem.salience:.2f} | Tags: {', '.join(mem.tags or [])}")
            print()

    # Display patterns
    if results["patterns"]:
        print(f"\n[PATTERNS DETECTED] {len(results['patterns'])} patterns:")
        print("-" * 80)
        for pattern in results["patterns"]:
            print(f"  • {pattern}")
        print()

    # Display clusters
    if results["clusters"]:
        print(f"\n[CLUSTERS] {len(results['clusters'])} memory clusters:")
        print("-" * 80)
        for i, cluster in enumerate(results["clusters"], 1):
            print(f"  Cluster {i}: {len(cluster)} memories")
        print()

    # Summary
    print(f"\n[SUMMARY]")
    print("-" * 80)
    print(f"Total unique memories retrieved: {len(results['all_memories'])}")
    print(f"Primary (direct) matches: {len(results['primary_results'])}")
    print(f"Associated (lateral) memories: {len(results['associated_memories'])}")
    print(f"Clusters formed: {len(results['clusters'])}")
    print(f"Patterns detected: {len(results['patterns'])}")


def main():
    """Run the test."""
    print("=" * 80)
    print("ASSOCIATIVE MEMORY QUERYING TEST")
    print("=" * 80)

    # Create test system and add memories
    memory = create_test_memories()

    # Test regular search for comparison
    test_regular_search(memory)

    # Test associative search
    test_associative_search(memory)

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
