from queue import Queue
import signal
from socket import *
from threading import Thread
from time import sleep
import tkinter as tkt
from tkinter import messagebox
from typing import Callable
from DTOs import *
import utils

GATEWAY_ADDRESS = ('127.0.0.1', 8080)
background_thread: Thread
running: bool = True
connected: bool = False
gateway: socket
main_window: tkt.Tk
gateway_interface_drones_state_text: tkt.StringVar
selected_drone_id: tkt.StringVar
selected_shipping_address: tkt.StringVar

dispatch_queue: Queue[Callable] = Queue(maxsize=-1)

def SIGINT_handler(sig, frame):
    graceful_exit()


def graceful_exit(event=None):
    global running, connected, gateway, main_window

    print('\nTermino...')
    running = False
    if connected:
        connected = False
        gateway.shutdown(SHUT_RDWR)
    background_thread.join()
    gateway.close()
    main_window.destroy()
    main_window.quit()
    exit(0)


def dispatch_to_main_queue(code: Callable):
    dispatch_queue.put(code)

def update_GUI():
    while not dispatch_queue.empty():
        task = dispatch_queue.get_nowait()
        task()
    main_window.after(20, update_GUI)

def show_error(title: str = "Errore", message: str = "Si è verificato un errore"):
    dispatch_to_main_queue(lambda: messagebox.showerror(title, message))


def establish_connection():
    global gateway, connected, gateway_interface_drones_state_text

    while running and not connected :
        try:
            gateway = socket(AF_INET, SOCK_STREAM)
            gateway.connect(GATEWAY_ADDRESS)
            connected = True
            dispatch_to_main_queue(lambda: gateway_interface_drones_state_text.set(""))
            
        except error:
            gateway.close()
            dispatch_to_main_queue(lambda: gateway_interface_drones_state_text.set("Tentativo di connessione fallito.\nSto riprovando ogni due secondi..."))
            sleep(2)


def update_interface():
    global gateway, connected, gateway_interface_drones_state_text

    if not connected:
        establish_connection()
    while running and connected:
        data = utils.recv_one_message(gateway)
        if not data:
            def alert_and_quit():
                global connected

                messagebox.showerror("Errore", "Il Gateway si è disconnesso, termino il programma..")
                connected = False
                graceful_exit()
            dispatch_to_main_queue(alert_and_quit)
            break
        gateway_interface_DTO = GatewayInterfaceDTO.decode(data)
        if not gateway_interface_DTO.is_error:
            dispatch_to_main_queue(lambda: gateway_interface_drones_state_text.set(gateway_interface_DTO.message))
        else:
            show_error(message=gateway_interface_DTO.message)


def send(event=None):
    global gateway, selected_drone_id, selected_shipping_address
    
    if entries_are_valid():
        drone_id = int(selected_drone_id.get().strip())
        request = ShippingRequestDTO(drone_id, selected_shipping_address.get().strip())
        utils.send_message(gateway, request.encode())
        selected_drone_id.set("")
        selected_shipping_address.set("")
    else:
        messagebox.showerror("Errore", "Devi scegliere un drone presente nella lista e l'indirizzo non può essere vuoto o contenere la sequenza di caratteri \":::\"")


def entries_are_valid() -> bool:
    return selected_drone_id.get().isdigit() and not selected_shipping_address.get() == "" and not selected_shipping_address.get().__contains__(":::")


if __name__ == "__main__":

    main_window = tkt.Tk()
    main_window.after(100, update_GUI)
    main_window.title("Interfaccia Gateway")
    main_window.minsize(width=600, height=300)
    main_window.resizable(width=False, height=True)

    gateway_interface_frame = tkt.Frame(main_window)
    gateway_interface_frame.pack(fill=tkt.BOTH)

    gateway_interface_drones_state_text = tkt.StringVar()
    gateway_interface_drones_state_label = tkt.Label(gateway_interface_frame, textvariable=gateway_interface_drones_state_text, justify=tkt.LEFT)
    gateway_interface_drones_state_label.pack(side=tkt.LEFT, fill=tkt.BOTH, padx=10, pady=10)

    input_frame = tkt.Frame(main_window)
    input_frame.pack(fill=tkt.X, side=tkt.BOTTOM, padx=10, pady=10)

    drone_id_entry_label = tkt.Label(input_frame, text="ID Drone:")
    drone_id_entry_label.pack(side=tkt.LEFT)

    selected_drone_id = tkt.StringVar()
    drone_id_entry = tkt.Entry(input_frame, textvariable=selected_drone_id, width=4)
    drone_id_entry.bind("<Return>", send)
    drone_id_entry.pack(side=tkt.LEFT)

    shipping_address_label = tkt.Label(input_frame, text="Indirizzo:")
    shipping_address_label.pack(side=tkt.LEFT)

    selected_shipping_address = tkt.StringVar()
    entry_field = tkt.Entry(input_frame, textvariable=selected_shipping_address)
    entry_field.bind("<Return>", send)
    entry_field.pack(side=tkt.LEFT, fill=tkt.X, expand=True)

    send_button = tkt.Button(input_frame, text="Invio", command=send)
    send_button.pack(side=tkt.RIGHT)

    main_window.protocol("WM_DELETE_WINDOW", graceful_exit)
    signal.signal(signal.SIGINT, SIGINT_handler)

    background_thread = Thread(target=update_interface)
    background_thread.start()

    tkt.mainloop()
    