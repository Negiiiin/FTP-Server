import time
from socket import *
import threading
import sys
import os
import json


MAXLISTEN = 15
EOF = chr(26)
MAXMSGLEN = 1000

#--------------------------------------------------------------

def recvNextMsg(msgSocket, inputBuffer):
    data = tmp = ""
    msg = ""
    while True:
        data = msgSocket.recv(MAXMSGLEN)
        inputBuffer = inputBuffer + data
        
        if len(inputBuffer) % 2 == 1:
            continue

        for i in range(0, len(inputBuffer)):
            if i % 2 == 1:
                msg = msg + inputBuffer[i]
            else:
                if inputBuffer[i] == '1':
                    return msg, inputBuffer[i+2:]
        inputBuffer = ""
        
                
#--------------------------------------------------------------
#--------------------------------------------------------------

def sendMsg(message):
    msgSocket.sendall(message + EOF)
    return

#--------------------------------------------------------------
#--------------------------------------------------------------

file = open ('etc/config.json', "r") 
config = json.loads(file.read())
msgPort = config['commandChannelPort']
filePort = config['dataChannelPort']
file.close()

PORT = -1
while True:
    try:
        PORT = int(raw_input("Enter port number: "))
        if PORT <= 0 or PORT >= 65535:
            print("500 enter a between 1 and 65534")
            continue
        break
    except ValueError:
        print("500 enter a number")
PATH = "clients/" + str(PORT)
if not os.path.exists(PATH):
    os.makedirs(str(PATH))
PATH += "/"

msgSocket = socket(AF_INET, SOCK_STREAM)
msgSocket.bind(("", PORT))
try :
    msgSocket.connect(("", msgPort))
except error:
    print("500 could not establish connection to server")
    msgSocket.close()
    sys.exit()

fileSocket = socket(AF_INET, SOCK_STREAM)
fileSocket.bind(("", PORT + 1))

try:
    fileSocket.connect(("", filePort))
except error:
    print("500 could not establish connection to server")
    msgSocket.close()
    fileSocket.close()
    sys.exit()


data = inputBuffer = fileData = fileBuffer = ""
data, inputBuffer = recvNextMsg(msgSocket, inputBuffer) 
print(data)
while True:
    try:
        cmd = raw_input("your next command: ")
        sendMsg(cmd)
        data, inputBuffer = recvNextMsg(msgSocket, inputBuffer) 
        print(data)
        if data[0:3] == "332":
            continue
        if data[0:3] == "500":
            continue
        if data[0:3] == "550":
            continue
        if data[0:3] == "501":
            continue
        if data[0:3] == "425":
            continue
            
        if cmd == "QUIT":
            sys.exit()
        if cmd == "LIST":
            fileData, fileBuffer = recvNextMsg(fileSocket, fileBuffer)
            print (fileData)
        if ( cmd[0:2] == "DL" ):
            f = open(PATH + cmd[3:len(cmd)],"w+")
            fileData, fileBuffer = recvNextMsg(fileSocket, fileBuffer)
            f.write(fileData)
            f.close()
            data, inputBuffer = recvNextMsg(msgSocket, inputBuffer)
            print(data)
    except:
        msgSocket.close()
        fileSocket.close()
        sys.exit()

