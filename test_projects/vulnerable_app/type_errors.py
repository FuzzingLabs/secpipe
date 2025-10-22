#!/usr/bin/env python3
# Copyright (c) 2025 FuzzingLabs
#
# Licensed under the Business Source License 1.1 (BSL). See the LICENSE file
# at the root of this repository for details.
#
# After the Change Date (four years from publication), this version of the
# Licensed Work will be made available under the Apache License, Version 2.0.
# See the LICENSE-APACHE file or http://www.apache.org/licenses/LICENSE-2.0
#
# Additional attribution and requirements are provided in the NOTICE file.

"""
Test file with type errors for Mypy testing.
"""

from typing import List, Dict


def add_numbers(a: int, b: int) -> int:
    """Add two integers"""
    # Type error: returning string instead of int
    return str(a + b)


def process_items(items: List[str]) -> None:
    """Process a list of strings"""
    # Type error: iterating over None
    for item in items:
        print(item.upper())

    # Type error: passing int to function expecting string list
    process_items(123)


def get_user_data() -> Dict[str, str]:
    """Get user data"""
    # Type error: returning wrong type
    return ["user1", "user2"]


def calculate_total(numbers: List[int]) -> float:
    """Calculate total"""
    # Type error: calling method that doesn't exist
    return numbers.sum()


class User:
    def __init__(self, name: str, age: int):
        self.name = name
        self.age = age


def create_user(name: str, age: int) -> User:
    """Create a user"""
    # Type error: returning dict instead of User
    return {"name": name, "age": age}


# Missing type annotations
def unsafe_function(x, y):
    return x + y
