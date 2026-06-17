"""
utils/network.py — 网络工具 (W14 新增)

- 探测本机局域网 IP（用于二维码 URL）
- 探测端口是否被占用（避免服务启动失败）

为什么用 UDP connect 探测 LAN IP?
  - gethostname/gethostbyname 在多网卡环境下返回 DNS 解析顺序的第一个，
    不一定是 LAN 可达的那个。
  - UDP connect 不真发包（无 ICMP / 无握手），但会让 OS 选路由表里「默认出口」
    网卡，然后 getsockname() 返回本机 IP。这个 IP 在大多数家用/办公网就是
    LAN 网卡 IP，演示时手机连同一 Wi-Fi 就能访问。
"""
import logging
import socket

log = logging.getLogger(__name__)


def get_lan_ip() -> str:
    """探测本机局域网 IP（启发式：连 DNS 探默认出口，不实际发包）。

    W15+ 修复: 原版用 Google DNS 8.8.8.8, 国内组员无外网时 UDP connect 会
    阻塞 3-5s 然后 OSError 兜底返 127.0.0.1 → 教师二维码 URL 是
    http://127.0.0.1:5180/... → **学生手机扫码连不上**。
    改用阿里 DNS 223.5.5.5 (国内通, 1.5s timeout), 失败 fallback 到
    socket.gethostbyname(socket.gethostname())。

    边界:
      - 完全离线（无默认路由）→ 返回 "127.0.0.1"
      - 多网卡但走同一默认路由 → 返回默认出口网卡 IP（演示够用）
      - 返回空字符串（极端）→ 兜底 "127.0.0.1"
    """
    # 首选: 阿里 DNS (国内通, 1.5s timeout, 避免无外网时阻塞)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(1.5)
        s.connect(("223.5.5.5", 80))
        ip = s.getsockname()[0]
        if ip:
            return ip
    except OSError as e:
        log.warning("get_lan_ip: UDP connect 阿里 DNS 失败 (%s), 尝试 fallback", e)
    finally:
        s.close()

    # Fallback 1: socket.gethostbyname(gethostname())
    #   多网卡环境下可能返 192.168.x.x 或 10.x.x.x (LAN 内), 也可能返
    #   127.0.0.1 (主机名解析到回环), 但比 Google DNS 国内可达
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except OSError as e:
        log.warning("get_lan_ip: gethostbyname fallback 失败 (%s)", e)

    # Fallback 2: 兜底返 127.0.0.1, 教师能看到提示"二维码 URL 是回环地址,
    # 手机连不上请检查网络"
    log.warning("get_lan_ip: 所有探测失败, 兜底返 127.0.0.1 (手机扫码可能连不上)")
    return "127.0.0.1"


def is_port_free(port: int, host: str = "0.0.0.0") -> bool:
    """探测 host:port 是否可用（没被占用）。

    实现：尝试 bind，成功 = 空闲，OSError (EADDRINUSE) = 被占用。

    Args:
        port: 端口号
        host: 默认 "0.0.0.0"（IPv4 全部接口）

    Returns:
        True 端口空闲 / False 被占用
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # SO_REUSEADDR 让"刚被释放"的端口也能 bind（TIME_WAIT 状态），
        # 减少演示时反复开关弹窗导致端口不可用的概率。
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()
