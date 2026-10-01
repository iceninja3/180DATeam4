import pygame
import random

# Initialize Pygame
pygame.init()

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
CYAN = (0, 255, 255)
BLUE = (0, 0, 255)
ORANGE = (255, 165, 0)
YELLOW = (255, 255, 0)
GREEN = (0, 255, 0)
PURPLE = (128, 0, 128)
RED = (255, 0, 0)

COLORS = [CYAN, BLUE, ORANGE, YELLOW, GREEN, PURPLE, RED]

# Screen dimensions
SCREEN_WIDTH = 300
SCREEN_HEIGHT = 600
BLOCK_SIZE = 30

# Grid dimensions
GRID_WIDTH = SCREEN_WIDTH // BLOCK_SIZE
GRID_HEIGHT = SCREEN_HEIGHT // BLOCK_SIZE

# Shapes
SHAPES = [
    [[1, 1, 1, 1]], # I
    [[1, 0, 0], [1, 1, 1]], # J
    [[0, 0, 1], [1, 1, 1]], # L
    [[1, 1], [1, 1]], # O
    [[0, 1, 1], [1, 1, 0]], # S
    [[0, 1, 0], [1, 1, 1]], # T
    [[1, 1, 0], [0, 1, 1]]  # Z
]

class Tetromino:
    def __init__(self, x, y, shape):
        self.x = x
        self.y = y
        self.shape = shape
        self.color = COLORS[SHAPES.index(shape)]
        self.rotation = 0

    def image(self):
        return self.shape

    def rotate(self):
        # Rotate the shape 90 degrees clockwise
        self.shape = [list(row) for row in zip(*self.shape[::-1])]

class Tetris:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.grid = [[0 for _ in range(width)] for _ in range(height)]
        self.current_piece = self.new_piece()
        self.game_over = False
        self.score = 0

    def new_piece(self):
        shape = random.choice(SHAPES)
        return Tetromino(self.width // 2 - len(shape[0]) // 2, 0, shape)

    def valid_space(self, piece, x_offset=0, y_offset=0):
        for y, row in enumerate(piece.image()):
            for x, cell in enumerate(row):
                if cell:
                    new_x = piece.x + x + x_offset
                    new_y = piece.y + y + y_offset
                    if new_x < 0 or new_x >= self.width or new_y >= self.height or (new_y >= 0 and self.grid[new_y][new_x]):
                        return False
        return True

    def lock_piece(self, piece):
        for y, row in enumerate(piece.image()):
            for x, cell in enumerate(row):
                if cell:
                    if piece.y + y >= 0:
                        self.grid[piece.y + y][piece.x + x] = piece.color
        self.clear_lines()
        self.current_piece = self.new_piece()
        if not self.valid_space(self.current_piece):
            self.game_over = True

    def clear_lines(self):
        lines_to_clear = []
        for y in range(self.height):
            if all(self.grid[y]):
                lines_to_clear.append(y)
        
        for line in lines_to_clear:
            del self.grid[line]
            self.grid.insert(0, [0 for _ in range(self.width)])
        
        self.score += len(lines_to_clear) * 100

    def move_down(self):
        if self.valid_space(self.current_piece, y_offset=1):
            self.current_piece.y += 1
        else:
            self.lock_piece(self.current_piece)

    def move_left(self):
        if self.valid_space(self.current_piece, x_offset=-1):
            self.current_piece.x -= 1

    def move_right(self):
        if self.valid_space(self.current_piece, x_offset=1):
            self.current_piece.x += 1

    def rotate_piece(self):
        # Save old shape in case rotation is invalid
        old_shape = [row[:] for row in self.current_piece.shape]
        self.current_piece.rotate()
        if not self.valid_space(self.current_piece):
            self.current_piece.shape = old_shape

def draw_grid(surface, grid):
    for y in range(len(grid)):
        for x in range(len(grid[y])):
            if grid[y][x]:
                pygame.draw.rect(surface, grid[y][x], (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE), 0)
            pygame.draw.rect(surface, WHITE, (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE), 1)

def draw_piece(surface, piece):
    for y, row in enumerate(piece.image()):
        for x, cell in enumerate(row):
            if cell:
                pygame.draw.rect(surface, piece.color, ((piece.x + x) * BLOCK_SIZE, (piece.y + y) * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE), 0)

def main():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Tetris")
    clock = pygame.time.Clock()
    game = Tetris(GRID_WIDTH, GRID_HEIGHT)

    fall_time = 0
    fall_speed = 500 # ms

    run = True
    while run:
        screen.fill(BLACK)
        fall_time += clock.get_rawtime()
        clock.tick()

        if fall_time >= fall_speed:
            fall_time = 0
            game.move_down()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    game.move_left()
                if event.key == pygame.K_RIGHT:
                    game.move_right()
                if event.key == pygame.K_DOWN:
                    game.move_down()
                if event.key == pygame.K_UP:
                    game.rotate_piece()

        draw_grid(screen, game.grid)
        draw_piece(screen, game.current_piece)
        
        if game.game_over:
            font = pygame.font.SysFont('comicsans', 60, True)
            label = font.render('GAME OVER', 1, WHITE)
            screen.blit(label, (SCREEN_WIDTH // 2 - label.get_width() // 2, SCREEN_HEIGHT // 2 - label.get_height() // 2))
            pygame.display.update()
            pygame.time.delay(2000)
            run = False

        pygame.display.update()

    pygame.quit()

if __name__ == "__main__":
    main()
