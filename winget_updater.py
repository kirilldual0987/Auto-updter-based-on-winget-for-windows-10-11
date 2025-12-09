"""
winget‑updater.py

A PyQt5 application that:

1. Checks if the script is running with administrator privileges.
   If not – restarts itself via UAC (requires user consent).

2. Checks if the Windows Package Manager (winget) is installed.
   If winget is missing, downloads the latest public build of
   Microsoft Desktop App Installer (file *.msixbundle) from the official mirror
   and installs it using the PowerShell command Add‑AppxPackage.

3. Once winget is guaranteed to be available, automatically runs:
   winget upgrade --all --accept-source‑agreements
   --accept-package‑agreements --disable-interactivity

4. All output is shown in a QTextEdit widget, with a progress indicator
   displaying that the process is running. The user does not have to click anything –
   everything happens automatically.

Requirements
----------
* Windows 10 1809 + or Windows 11 (winget support)
* Python 3.6 or newer
* PyQt5 (`pip install PyQt5`)
* Internet connection to download the msix package (≈ 15 MB)

Running
-------
Run the file as a normal user – the script will request UAC and obtain administrator
rights automatically:

    python winget_updater.py
"""

import sys
import os
import shutil
import platform
import ctypes
import urllib.request
import tempfile
import threading
import subprocess

from PyQt5.QtCore import Qt, QTimer, QProcess, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QProgressBar,
    QMessageBox,
)


WINGET_MSIX_URL = (
    "https://sourceforge.net/projects/windows-package-manager.mirror"
    "/files/v1.11.430/Microsoft.DesktopAppInstaller_8wekyb3d8bbwe.msixbundle/download"
)

WINGET_UPDATE_ARGS = [
    "upgrade",
    "--all",
    "--accept-source-agreements",
    "--accept-package-agreements",
    "--disable-interactivity",
]


def a7B2cD3() -> bool:
    """Check if the process is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def e9F1gH4() -> None:
    """Relaunch the current script with UAC (runas)."""
    params = " ".join([f'"{arg}"' for arg in sys.argv])
    ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        params,
        None,
        1,
    )
    sys.exit(0)


def i5J6kL7() -> bool:
    """Return True if winget is already in PATH."""
    return shutil.which("winget") is not None


def m8N9oP0(url: str, dest_path: str, progress_cb=None):
    """
    Download file from HTTP(S) to dest_path.
    progress_cb(block_num, block_size, total_size) is called during download.
    """
    urllib.request.urlretrieve(url, dest_path, reporthook=progress_cb)


class WorkerSignals(QObject):
    log = pyqtSignal(str)
    progress = pyqtSignal(int)          # from 0 to 100
    finished = pyqtSignal(bool, str)     # success, message


class WingetUpdater(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Winget – Full Automatic Update")
        self.resize(720, 500)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout()
        central.setLayout(main_layout)

        self.status_label = QLabel("Initializing…")
        main_layout.addWidget(self.status_label)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)
        main_layout.addWidget(self.log_view, stretch=1)

        self.progress = QProgressBar()
        self.progress.setMaximum(0)          # 0 → indeterminate
        self.progress.setVisible(False)
        main_layout.addWidget(self.progress)

        self.winget_process = QProcess(self)
        self.winget_process.setProcessChannelMode(QProcess.MergedChannels)
        self.winget_process.readyReadStandardOutput.connect(self.f6G7h8)
        self.winget_process.finished.connect(self.i9J0k1)

        QTimer.singleShot(0, self.q1R2s3)

    def q1R2s3(self):
        """Main sequential set of steps."""
        if platform.system() != "Windows":
            self.o5P6q7("This program runs only on Windows.")
            return
        if platform.release() not in ("10", "11"):
            self.o5P6q7("Only Windows 10 and Windows 11 are supported.")
            return

        if not a7B2cD3():
            self.l2M3n4("Requesting administrator privileges...")
            e9F1gH4()

        self.l2M3n4("Checking for winget...")
        if i5J6kL7():
            self.l2M3n4("winget already installed, proceeding to update.")
            QTimer.singleShot(200, self.c3D4e5)
        else:
            self.l2M3n4("winget NOT found – starting download and installation.")
            self.t4U5v6()

    def t4U5v6(self):
        """Download and install App Installer (winget)."""
        self.progress.setMaximum(0)
        self.progress.setVisible(True)

        self.msix_path = os.path.join(
            tempfile.gettempdir(),
            "Microsoft.DesktopAppInstaller_8wekyb3d8bbwe.msixbundle",
        )

        self.inst_worker = threading.Thread(target=self.w7X8y9)
        self.inst_worker.start()

    def w7X8y9(self):
        """Background thread – download + install."""
        signals = WorkerSignals()
        signals.log.connect(self.l2M3n4)
        signals.progress.connect(self.r8S9t0)
        signals.finished.connect(self.z0A1b2)

        try:
            def reporthook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = int(block_num * block_size * 100 / total_size)
                    signals.progress.emit(percent)

            signals.log.emit(f"Downloading msix package… ({WINGET_MSIX_URL})")
            m8N9oP0(WINGET_MSIX_URL, self.msix_path, progress_cb=reporthook)
            signals.log.emit(f"Saved to {self.msix_path}")

            signals.log.emit("Installing App Installer package (winget)…")
            ps_cmd = (
                f"Add-AppxPackage -Path '{self.msix_path}' -ForceApplicationShutdown"
            )
            proc = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    ps_cmd,
                ],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                err = proc.stderr.strip() or proc.stdout.strip()
                signals.finished.emit(False, f"Failed to install winget:\n{err}")
                return

            signals.log.emit("Installation completed successfully.")
            signals.finished.emit(True, "winget installed")
        except Exception as exc:
            signals.finished.emit(False, f"Error: {exc}")

    def z0A1b2(self, success: bool, message: str):
        """Handler for winget installation completion."""
        self.progress.setVisible(False)
        self.progress.setMaximum(0)

        if success:
            self.l2M3n4("winget successfully installed, proceeding to update.")
            QTimer.singleShot(500, self.c3D4e5)
        else:
            self.o5P6q7(f"winget installation failed.\n{message}")

    def c3D4e5(self):
        """Launch winget upgrade --all."""
        self.u1V2w3(False)
        self.log_view.append("\n--- Starting update of all packages ---")
        self.status_label.setText("Updating...")
        self.progress.setMaximum(0)
        self.progress.setVisible(True)

        self.winget_process.start("winget", WINGET_UPDATE_ARGS)

        if not self.winget_process.waitForStarted(3000):
            self.l2M3n4("<b>Error:</b> Failed to start winget.")
            self.x4Y5z6()

    def f6G7h8(self):
        """Read stdout+stderr from winget and output to log."""
        data = self.winget_process.readAllStandardOutput()
        text = bytes(data).decode(errors="replace")
        self.log_view.append(text.rstrip())

    def i9J0k1(self, exit_code: int, exit_status):
        """Handler for winget process completion."""
        self.progress.setVisible(False)
        self.u1V2w3(True)

        if exit_status == QProcess.NormalExit and exit_code == 0:
            self.status_label.setText("Update completed successfully")
            self.log_view.append("\n--- Update completed without errors ---")
        else:
            self.status_label.setText(f"Update error (code={exit_code})")
            self.log_view.append(f"\n--- Finished with error (code={exit_code}) ---")
            QMessageBox.warning(
                self,
                "Winget Error",
                f"The update finished with an error (code={exit_code}).\n"
                "See the log above for details.",
            )

    def l2M3n4(self, msg: str):
        """Add a line to QTextEdit without blocking UI."""
        self.log_view.append(msg)

    def o5P6q7(self, msg: str):
        """Show a critical error and quit the application."""
        self.l2M3n4(f"<b>Fatal error:</b> {msg}")
        QMessageBox.critical(self, "Error", msg)
        QApplication.instance().quit()

    def r8S9t0(self, percent: int):
        """Set percent indicator (during msix download)."""
        if not self.progress.isVisible():
            self.progress.setVisible(True)
        self.progress.setMaximum(100)
        self.progress.setValue(percent)

    def u1V2w3(self, enabled: bool):
        """Toggle the visibility of the progress indicator."""
        self.progress.setVisible(not enabled)

    def x4Y5z6(self):
        self.progress.setVisible(False)
        self.u1V2w3(True)
        self.status_label.setText("Launch error")


def A7b8C9():
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    window = WingetUpdater()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    A7b8C9()

