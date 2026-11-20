def codificar_arinc429(valor: float, minimo: float, maximo: float, label_octal: int = 0o203, sdi: int = 0, ssm: int = 0b11) -> dict:
    if maximo <= minimo:
        raise ValueError("El máximo debe ser mayor que el mínimo.")
    if valor < minimo or valor > maximo:
        raise ValueError(f"El valor {valor} está fuera del rango permitido [{minimo}, {maximo}].")

    max_data = (1 << 19) - 1
    proporcion = (valor - minimo) / (maximo - minimo)
    data_19 = int(round(proporcion * max_data)) & max_data

    label_8 = label_octal & 0xFF
    sdi_2 = sdi & 0x3
    ssm_2 = ssm & 0x3

    palabra_31 = (
        label_8
        | (sdi_2 << 8)
        | (data_19 << 10)
        | (ssm_2 << 29)
    )

    unos = palabra_31.bit_count()
    paridad = 0 if (unos % 2 == 1) else 1
    palabra_32 = palabra_31 | (paridad << 31)

    return {
        "palabra_32_int": palabra_32,
        "hex": f"0x{palabra_32:08X}",
        "bin": f"{palabra_32:032b}",
        "bytes_4": list(palabra_32.to_bytes(4, byteorder="big")),
        "campos": {
            "label_octal": f"{label_8:03o}",
            "label_bin": f"{label_8:08b}",
            "sdi_bin": f"{sdi_2:02b}",
            "data_19_int": data_19,
            "data_19_bin": f"{data_19:019b}",
            "ssm_bin": f"{ssm_2:02b}",
            "parity": paridad,
        },
    }
