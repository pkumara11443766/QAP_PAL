import subprocess
import sys
import os
import time
import msvcrt
from console_utils import enable_ansi_windows, press_enter, Colors

class CIGitUpdater:
    try:
        import config_manager
        TARGET = config_manager.CI_GIT_BASE
    except ImportError:
        TARGET = r"C:\Intel\ci.git"

    def __init__(self, programming_mode=False):
        enable_ansi_windows()
        os.environ["GIT_TERMINAL_PROMPT"] = "0"
        self.programming_mode = programming_mode
            
    def run_live(self, cmd):
        try:
            process = subprocess.Popen(cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                bufsize=1, 
                encoding='utf-8', 
                errors='replace'
            )
            for line in iter(process.stdout.readline, ''):
                print(line, end='')
            process.stdout.close()
            process.wait()
            return process.returncode

        except FileNotFoundError:
            print(f"{Colors.RED}ERROR: Git executable not found. Ensure Git is installed and in your PATH.{Colors.RESET}")
            return 1
        except Exception as e:
            print(f"{Colors.RED}ERROR: Failed to run command: {e}{Colors.RESET}")
            return 1

    def _configure_git(self):
        safe_target = self.TARGET.replace('\\', '/')
        try:
            output = subprocess.check_output(
                ["git", "config", "--global", "--get-all", "safe.directory"], 
                stderr=subprocess.DEVNULL, text=True
            )
            if safe_target.lower() in [line.strip().lower() for line in output.splitlines()]: return
        except (subprocess.CalledProcessError, FileNotFoundError): pass
        self.run_live(["git", "config", "--global", "--add", "safe.directory", safe_target])

    def _clone_repo(self):
        print(f"{Colors.YELLOW}ci.git not found at '{self.TARGET}'. Attempting clone...{Colors.RESET}")
        
        ret = self.run_live(["git", "lfs", "install", "--skip-smudge"])
        if ret != 0:
            print(f"{Colors.RED}FAILED TO INSTALL GIT LFS{Colors.RESET}")
            press_enter()
            sys.exit(1)
        
        clone_cmd = ['git', 'clone', "https://github.com/intel-innersource/applications.infrastructure.capi.ci.git", self.TARGET]
        ret = self.run_live(clone_cmd)
        
        if ret != 0:
            print(f"{Colors.RED}FAILED TO CLONE ci.git (Exit code: {ret}). Check your Git credentials and network access.{Colors.RESET}")
            press_enter()
            sys.exit(1)

    def _check_local_changes(self):
        try:
            process = subprocess.Popen(
                ['git', '-C', self.TARGET, 'status', '--porcelain'],
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                creationflags=0x08000000
            )
            output, _ = process.communicate()
            
            if output and output.strip():
                print(f"{Colors.YELLOW}Local modifications detected in {self.TARGET}:{Colors.RESET}")
                lines = output.strip().splitlines()
                for line in lines[:10]:
                    print(f"  {line}")
                if len(lines) > 10:
                    print(f"  ... and {len(lines)-10} more.")
                
                print(f"\n{Colors.YELLOW}These changes differ from the repository.{Colors.RESET}")
                print("Do you want to overwrite these files to match the repo? (y/n): ", end="", flush=True)
                
                while True:
                    choice = msvcrt.getch().lower()
                    if choice in [b'y', b'n']:
                        print(choice.decode('utf-8'))
                        break
                
                if choice == b'y':
                    print(f"{Colors.CYAN}Overwriting local changes...{Colors.RESET}")
                    self.run_live(['git', '-C', self.TARGET, 'reset', '--hard'])
                    self.run_live(['git', '-C', self.TARGET, 'clean', '-f', '-d'])
                    return True
                else:
                    print(f"{Colors.YELLOW}Keeping local changes. Update will attempt merge.{Colors.RESET}")
                    return False
            return True
        except Exception:
            return True

    def _update_repo(self, allow_auto_reset=True):
        print(f"{Colors.CYAN}Pulling latest changes for {self.TARGET}...{Colors.RESET}")
        pull_cmd = ['git', '-C', self.TARGET, 'pull']
        ret = self.run_live(pull_cmd)
        
        if ret != 0:
            if not allow_auto_reset:
                print(f"{Colors.RED}FAILED TO UPDATE ci.git (Exit code: {ret}).{Colors.RESET}")
                print(f"{Colors.YELLOW}Auto-reset skipped because local changes were preserved.{Colors.RESET}")
                if self.programming_mode:
                    sys.exit(1)
                else:
                    press_enter()
                    sys.exit(1)

            print(f"{Colors.RED}FAILED TO UPDATE ci.git (Exit code: {ret}). Attempting to reset and pull...{Colors.RESET}")
            self.run_live(['git', '-C', self.TARGET, 'reset', '--hard'])
            self.run_live(['git', '-C', self.TARGET, 'clean', '-f', '-d'])
            
            ret = self.run_live(pull_cmd)
            
            if ret != 0:
                print(f"{Colors.RED}FAILED TO UPDATE ci.git after reset (Exit code: {ret}).{Colors.RESET}")
                if self.programming_mode:
                    print(f"{Colors.YELLOW}Git pull failed. Repo may be out of date. Programming may fail.{Colors.RESET}")
                    print("Press Enter to continue or any other key to exit.")
                    if msvcrt.getch() == b'\r':
                        sys.exit(0)
                    else:
                        sys.exit(1)
                else:
                    press_enter()
                    sys.exit(1)

    def run(self):
        try:
            self._configure_git()
            if not os.path.isdir(self.TARGET):
                self._clone_repo()
            else:
                is_clean = self._check_local_changes()
                self._update_repo(allow_auto_reset=is_clean)
            time.sleep(3)
            sys.exit(0)

        except KeyboardInterrupt:
            sys.exit(1)

if __name__ == "__main__":
    programming_mode = "--programming" in sys.argv
    updater = CIGitUpdater(programming_mode)
    updater.run()