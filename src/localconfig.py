from socket import gethostname

lora_hat_config = {
    "module_address": int(gethostname()[4:8]),
    "target_address": 0xFFFF,
}
