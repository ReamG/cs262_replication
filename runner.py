from connections import consts
from multiprocessing import Process
from server import create_server


def run_model():
    pA = Process(target=create_server, args=("A"))
    pB = Process(target=create_server, args=("B"))
    pC = Process(target=create_server, args=("C"))

    pA.start()
    pB.start()
    pC.start()

    print("here1")
    pA.join()
    pB.join()
    pC.join()
    print("here")


if __name__ == "__main__":
    run_model()
