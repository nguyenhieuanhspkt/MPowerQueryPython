import sys
import os

# ensure project root is on path when run from any directory
sys.path.insert(0, os.path.dirname(__file__))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('MPowerQueryPython')
    app.setFont(QFont('Segoe UI', 9))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
