import sys
import json
import matplotlib.pyplot as plt
import random

ROOM_WIDTH = 30
ROOM_HEIGHT = 40

# Furniture dimensions
FURNITURE_SIZES = {
    "bed": (6, 8),
    "desk": (4, 2),
    "tv": (4, 2),
    "wardrobe": (4, 2)
}

class Furniture:
    def __init__(self, name, x, y, width, height, orientation):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.orientation = orientation
        self.interact_position = self.get_interact_position()

    def get_interact_position(self):
        if self.orientation == 0:
            return (self.x, self.y - self.height // 2)
        elif self.orientation == 90:
            return (self.x + self.width // 2, self.y)
        elif self.orientation == 180:
            return (self.x, self.y + self.height // 2)
        else:
            return (self.x - self.width // 2, self.y)

def generate_room_layout(furniture_counts):
    furniture_list = []
    wall_positions = [
        (0, ROOM_HEIGHT / 2),
        (ROOM_WIDTH, ROOM_HEIGHT / 2),
        (ROOM_WIDTH / 2, 0),
        (ROOM_WIDTH / 2, ROOM_HEIGHT)
    ]
    orientations = [270, 90, 0, 180]

    for name, count in furniture_counts.items():
        width, height = FURNITURE_SIZES[name]
        for i in range(count):
            wall_index = len(furniture_list) % len(wall_positions)
            x, y = wall_positions[wall_index]
            orientation = orientations[wall_index]
            if orientation == 0:
                y += height / 2
            elif orientation == 180:
                y -= height / 2
            elif orientation == 90:
                x -= width / 2
            elif orientation == 270:
                x += width / 2
            x = min(max(x, width / 2), ROOM_WIDTH - width / 2)
            y = min(max(y, height / 2), ROOM_HEIGHT - height / 2)
            overlap = True
            attempts = 0
            while overlap and attempts < 100:
                overlap = False
                for other in furniture_list:
                    if (abs(other.x - x) < (other.width + width) / 2) and (abs(other.y - y) < (other.height + height) / 2):
                        overlap = True
                        x = random.uniform(width / 2, ROOM_WIDTH - width / 2)
                        y = random.uniform(height / 2, ROOM_HEIGHT - height / 2)
                        break
                attempts += 1
            furniture = Furniture(name, x, y, width, height, orientation)
            furniture_list.append(furniture)

    return furniture_list

def plot_room_layout(furniture_list, notes):
    fig, ax = plt.subplots()
    ax.set_xlim(0, ROOM_WIDTH)
    ax.set_ylim(0, ROOM_HEIGHT)
    ax.set_aspect('equal')
    ax.set_title("Room Layout")
    ax.set_xlabel("Width (feet)")
    ax.set_ylabel("Height (feet)")

    ax.plot([0, ROOM_WIDTH, ROOM_WIDTH, 0, 0], [0, 0, ROOM_HEIGHT, ROOM_HEIGHT, 0], color='black')

    for furniture in furniture_list:
        x, y = furniture.x, furniture.y
        width, height = furniture.width, furniture.height
        rect = plt.Rectangle((x - width / 2, y - height / 2), width, height, edgecolor='blue', facecolor='lightblue', label=furniture.name)
        ax.add_patch(rect)
        ax.text(x, y, furniture.name, ha='center', va='center', fontsize=8, color='black')

        if furniture.orientation == 0:
            ax.arrow(x, y, 0, -height / 4, head_width=0.5, head_length=0.5, fc='red', ec='red')
        elif furniture.orientation == 90:
            ax.arrow(x, y, width / 4, 0, head_width=0.5, head_length=0.5, fc='red', ec='red')
        elif furniture.orientation == 180:
            ax.arrow(x, y, 0, height / 4, head_width=0.5, head_length=0.5, fc='red', ec='red')
        elif furniture.orientation == 270:
            ax.arrow(x, y, -width / 4, 0, head_width=0.5, head_length=0.5, fc='red', ec='red')

    if notes:
        ax.text(0.5, -0.1, f"Notes: {notes}", transform=ax.transAxes, ha='center', va='top', fontsize=10, color='gray')

    plt.savefig('room_layout.png')
    plt.close()

def main():
    args = sys.argv[1:]
    bed = int(args[0])
    desk = int(args[1])
    tv = int(args[2])
    wardrobe = int(args[3])
    notes = args[4]

    furniture_counts = {
        "bed": bed,
        "desk": desk,
        "tv": tv,
        "wardrobe": wardrobe
    }

    furniture_list = generate_room_layout(furniture_counts)
    plot_room_layout(furniture_list, notes)

    print("room_layout.png")

if __name__ == "__main__":
    main()

