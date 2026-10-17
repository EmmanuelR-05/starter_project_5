import random
import sys

# Approximate English letter frequencies
LETTER_FREQ = {
    "A": 0.078, "B": 0.02, "C": 0.04, "D": 0.038, "E": 0.11, "F": 0.014,
    "G": 0.03, "H": 0.023, "I": 0.089, "J": 0.0021, "K": 0.0097, "L": 0.053,
    "M": 0.027, "N": 0.072, "O": 0.061, "P": 0.028, "Q": 0.0019, "R": 0.073,
    "S": 0.087, "T": 0.067, "U": 0.033, "V": 0.01, "W": 0.0091, "X": 0.0027,
    "Y": 0.016, "Z": 0.0044,
}


def shuffle(word):
    """Fisher-Yates shuffle of the characters in a string."""
    a = list(word)
    for i in range(len(a) - 1, 0, -1):
        j = random.randint(0, i)
        a[i], a[j] = a[j], a[i]
    return "".join(a)


def chunk(array, size):
    """Split a sequence into pieces of the given size."""
    return [array[i:i + size] for i in range(0, len(array), size)]


def random_grid(size):
    """
    Build a size x size grid. size**3 letters are generated using the
    frequency table, split into size*size "dice" of `size` letters each,
    and one letter is rolled from each die.
    """
    total_chars = size * size * size

    letters = ""
    for letter, freq in LETTER_FREQ.items():
        letters += letter * round(freq * total_chars)

    # Pad with the most common letters if rounding left us short
    by_freq = sorted(LETTER_FREQ, key=LETTER_FREQ.get, reverse=True)
    for i in range(max(0, total_chars - len(letters))):
        letters += by_freq[i % len(by_freq)]

    # Shuffle first, then trim, so no letter is systematically dropped
    letters = shuffle(letters)[:total_chars]

    dice = chunk(letters, size)
    chars = [random.choice(die) for die in dice]
    random.shuffle(chars)

    grid = []
    for row in range(size):
        grid.append([])
        for col in range(size):
            letter = chars[size * row + col].upper()
            if letter == "Q":
                letter = "Qu"
            elif letter == "S":
                letter = "St"
            elif letter == "I":
                letter = "Ie"
            grid[row].append(letter)
    return grid


if __name__ == "__main__":
    print(random_grid(int(sys.argv[1])))
