import re

from .readJSONFile import read_json_to_list


class Boggle:
    def __init__(self, grid, dictionary):
        self.grid = grid
        self.dictionary = []
        self.solutions = []

        if isinstance(dictionary, list):
            self.dictionary = dictionary
        else:
            # Treat anything else as a path to a JSON dictionary file
            self.dictionary = read_json_to_list(dictionary)

    def getDictionary(self):
        return self.dictionary

    def is_grid_valid(self):
        # Allowed tiles: St, Qu, Ie, or any single letter except i, q, s
        regex = r"^((st|qu|ie)|[a-hj-prt-z])$"
        for row in self.grid:
            for cell in row:
                if not re.match(regex, cell.lower()):
                    return False
        return True

    def getSolution(self):
        self.solutions = []

        # 1. Validate inputs
        if self.grid is None or self.dictionary is None:
            return self.solutions

        N = len(self.grid)
        if N == 0:
            return self.solutions
        for row in self.grid:
            if len(row) != N:
                return self.solutions

        # Normalise case
        self.grid = [[x.upper() for x in row] for row in self.grid]
        self.dictionary = [x.upper() for x in self.dictionary]

        if not self.is_grid_valid():
            return self.solutions

        # 2. Build prefix map and search from every tile
        self.solution_set = set()
        self.hash_map = self.create_hash_map()

        for y in range(N):
            for x in range(N):
                visited = [[False] * N for _ in range(N)]
                self.find_words("", y, x, self.grid, visited,
                                self.hash_map, self.solution_set)

        self.solutions = list(self.solution_set)
        return self.solutions

    # Alias so both naming styles work
    get_solution = getSolution

    def find_words(self, word, y, x, grid, visited, hash_map, solution_set):
        adj = [[-1, -1], [-1, 0], [-1, 1], [0, 1],
               [1, 1], [1, 0], [1, -1], [0, -1]]

        # Out of bounds or already used on this path
        if y < 0 or x < 0 or y >= len(grid) or x >= len(grid) or visited[y][x]:
            return

        word += grid[y][x]

        # Prune: only continue if this is a prefix of (or is) a dictionary word
        if self.is_prefix_or_word(word, hash_map):
            visited[y][x] = True

            if self.is_word(word, hash_map) and len(word) >= 3:
                solution_set.add(word)

            for dy, dx in adj:
                self.find_words(word, y + dy, x + dx, grid, visited,
                                hash_map, solution_set)

        # Backtrack
        visited[y][x] = False

    def is_prefix_or_word(self, word, hash_map):
        return word in hash_map

    def is_word(self, word, hash_map):
        return hash_map.get(word) == 1

    def create_hash_map(self):
        """word -> 1 for real words, prefix -> 0 for prefixes only."""
        dict_map = {}
        for word in self.dictionary:
            dict_map[word] = 1
            for i in range(1, len(word)):
                prefix = word[:i]
                if prefix not in dict_map:
                    dict_map[prefix] = 0
        return dict_map


def main():
    grid = [["T", "W", "Y", "R"], ["E", "N", "P", "H"],
            ["G", "Z", "Qu", "R"], ["O", "N", "T", "A"]]
    dictionary = ["art", "ego", "gent", "get", "net", "new", "newt", "prat",
                  "pry", "qua", "quart", "quartz", "rat", "tar", "tarp", "ten",
                  "went", "wet", "arty", "rhr", "not", "quar"]
    print(Boggle(grid, dictionary).getSolution())


if __name__ == "__main__":
    # Run with:  python -m api.boggle_solver   (from the project folder)
    main()
