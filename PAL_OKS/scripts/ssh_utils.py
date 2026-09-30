import warnings

try:
    from cryptography.utils import CryptographyDeprecationWarning
except ImportError:
    CryptographyDeprecationWarning = DeprecationWarning

warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)

class SSHManager:
    def __init__(self, hostname, username, password, timeout=8):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout
        self.client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self):
        if self.client and self.client.get_transport() and self.client.get_transport().is_active():
            return
        import paramiko
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            self.hostname,
            username=self.username,
            password=self.password,
            timeout=self.timeout,
            banner_timeout=self.timeout,
            auth_timeout=self.timeout,
            allow_agent=False,
            look_for_keys=False
        )

    def disconnect(self):
        if self.client:
            self.client.close()
            self.client = None

    def exec_command(self, command, timeout=5):
        stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
        return stdin, stdout, stderr

def create_debug_user(ip, root_pass, debug_pass):
    if not all([ip, root_pass, debug_pass]):
        raise ValueError("BMC IP, Root Password, or Debug User Password missing.")

    with SSHManager(ip, "root", root_pass) as ssh:
        commands = [
            "ipmitool user set name 2 debuguser",
            f"ipmitool user set password 2 {debug_pass}",
            "ipmitool user enable 2",
            "ipmitool channel setaccess 1 2 ipmi=on privilege=4",
            "ipmitool channel setaccess 3 2 ipmi=on privilege=4"
        ]
        for cmd in commands:
            _, stdout, stderr = ssh.exec_command(cmd)
            if stdout.channel.recv_exit_status() != 0:
                err = stderr.read().decode().strip()
                safe_cmd = cmd.replace(debug_pass, '********') if debug_pass else cmd
                raise RuntimeError(f"Command failed: {safe_cmd}\nError: {err}")