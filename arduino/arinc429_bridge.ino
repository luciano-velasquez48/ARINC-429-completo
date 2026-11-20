const int PIN_TX_ARINC = 8;

void setup() {
  Serial.begin(9600);
  pinMode(PIN_TX_ARINC, OUTPUT);
  digitalWrite(PIN_TX_ARINC, LOW);
}

void transmitirPalabra32(uint32_t palabra) {
  for (int bit = 31; bit >= 0; bit--) {
    uint8_t val = (palabra >> bit) & 0x1;
    digitalWrite(PIN_TX_ARINC, val ? HIGH : LOW);
    delayMicroseconds(100);
  }
  digitalWrite(PIN_TX_ARINC, LOW);
}

void loop() {
  if (Serial.available() >= 4) {
    uint32_t palabra = 0;
    for (int i = 0; i < 4; i++) {
      palabra = (palabra << 8) | (uint8_t)Serial.read();
    }
    transmitirPalabra32(palabra);
  }
}
