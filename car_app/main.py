#Este codigo solo puede ser ejecutado con makecode, no tiene version de escritorio, solo web

def actualizar_motores():
    # Ambos motores avanzan
    if Vel_Izq >= 0 and Vel_Der >= 0:
        mbit_Robot.car_ctrl_speed2(mbit_Robot.CarState.CAR_RUN, Vel_Izq, Vel_Der)
    elif Vel_Izq < 0 and Vel_Der < 0:
        # Ambos motores van hacia atrás
        mbit_Robot.car_ctrl_speed2(mbit_Robot.CarState.CAR_BACK, abs(Vel_Izq), abs(Vel_Der))
    elif Vel_Izq < 0 and Vel_Der >= 0:
        # Giro sobre su propio eje a la izquierda (izq atrás, der adelante)
        mbit_Robot.car_ctrl_speed2(mbit_Robot.CarState.CAR_SPINLEFT, abs(Vel_Izq), Vel_Der)
    elif Vel_Izq >= 0 and Vel_Der < 0:
        # Giro sobre su propio eje a la derecha (izq adelante, der atrás)
        mbit_Robot.car_ctrl_speed2(mbit_Robot.CarState.CAR_SPINRIGHT, Vel_Izq, abs(Vel_Der))

def on_bluetooth_connected():
    basic.show_string("C")
bluetooth.on_bluetooth_connected(on_bluetooth_connected)

def on_bluetooth_disconnected():
    basic.show_string("D")
bluetooth.on_bluetooth_disconnected(on_bluetooth_disconnected)

def on_uart_data_received():
    global SerialString, Vel_Izq, Vel_Der
    SerialString = bluetooth.uart_read_until(serial.delimiters(Delimiters.NEW_LINE))
    if len(SerialString) > 0:
        prefijo = SerialString[0]
        # Si recibes L-100 o L100
        if prefijo == "L":
            Vel_Izq = int(SerialString.substr(1, len(SerialString) - 1))
            actualizar_motores()
        elif prefijo == "R":
            # Si recibes R-100 o R100
            Vel_Der = int(SerialString.substr(1, len(SerialString) - 1))
            actualizar_motores()
        elif prefijo == "z":
            Vel_Izq = 0
            Vel_Der = 0
            mbit_Robot.car_ctrl_speed2(mbit_Robot.CarState.CAR_STOP, 0, 0)
        elif prefijo == "x":
            mbit_Robot.RGB_Car_Big2(mbit_Robot.enColor.WHITE)
        else:
            mbit_Robot.RGB_Car_Big2(mbit_Robot.enColor.OFF)
bluetooth.on_uart_data_received(serial.delimiters(Delimiters.NEW_LINE),
    on_uart_data_received)

SerialString = ""
Vel_Der = 0
Vel_Izq = 0
# Inicialización
bluetooth.start_uart_service()
basic.show_string("OK")