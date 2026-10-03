from modules.config import FILTERED_DATA
from modules.exporter import export_comments_to_csv


def main():
    export_comments_to_csv(FILTERED_DATA)


if __name__ == "__main__":
    main()
