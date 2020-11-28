import time
from socket import *
import sys
import threading
import json
import os
import shutil
import logging
from datetime import *
import base64
from base64 import b64encode

MAILSERVER = "mail.ut.ac.ir"
EMAIL = "yourEmail@ut.ac.ir"
USERNAME = b'yourUsername'
PASSWORD = b'yourPassword!'

MAXLISTEN = 15
EOF = chr(26)
MAXMSGLEN = 1000
DEFAULTDIR = "./dir"
MINDIRLEN = 2

#--------------------------------------------------------------

commands = ['USER','PASS','PWD','MKD','RMD','LIST','CWD','DL','HELP','QUIT']
user = []
password = []
size = []
email = []
alert = []
admin = []
commandChannelPort = 0
dataChannelPort = 0
accountingEnable = False
accountingThreshold = 0
loggingEnable = False
loggingPath = ""
authorizationEnable = False
authorizationFiles = []

def preprocessUsers():
    global commandChannelPort, dataChannelPort, accountingEnable, accountingThreshold, loggingEnable, loggingPath, authorizationEnable, authorizationFiles
    file = open ('etc/config.json', "r") 
    config = json.loads(file.read())

    for i in config['users']: 
        user.append(i['user']) 
        password.append(i['password'])
        admin.append(0)

    for i in config['accounting']['users']:
        size.append(int(i['size']))
        email.append(i['email'])
        alert.append(i['alert'])

    for i in config['authorization']['admins']:
        for j in range (0, len(user)):
            if user[j] == i:
                admin[j] = 1

    commandChannelPort = config['commandChannelPort']
    dataChannelPort = config['dataChannelPort']
    accountingEnable = config['accounting']['enable']
    accountingThreshold = config['accounting']['threshold']
    loggingEnable = config['logging']['enable']
    loggingPath = config['logging']['path']
    authorizationEnable = config['authorization']['enable']

    for i in config['authorization']['files']:
        authorizationFiles.append(i)
    file.close()
    return

#--------------------------------------------------------------
#--------------------------------------------------------------

def writeLog(text):
    if loggingEnable == False:
        return
    with open(loggingPath, 'a') as log:
        log.write("{0} - {1}\n\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),str(text)))
    print("LOG:{0} - {1}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),str(text)))
    return

#--------------------------------------------------------------
#--------------------------------------------------------------

def recvNextMsg(msgSocket, inputBuffer):
    data = ""
    while True:
        inputBuffer = inputBuffer + data
        data = msgSocket.recv(MAXMSGLEN)
        for c in data:
            if c == EOF:
                left, right = data.split(EOF,1)
                msg = inputBuffer + left
                inputBuffer = right
                return msg, inputBuffer

#--------------------------------------------------------------
#--------------------------------------------------------------

def handle_client(msgSocket, fileSocket, address, connectionID):
    inputBuffer = ""
    loggedIn = False
    currentDirectory = DEFAULTDIR
    currentUsername = ""
    userID = 0
    
    sendMsg(msgSocket, "Connection established. \nenter HELP for command list." )
    while True:
        instruction, inputBuffer = recvNextMsg(msgSocket, inputBuffer)
        writeLog("Instruction received on connection: " + str(connectionID) + "\n" + instruction)
        instruction = instruction + " "
        data, inputs = instruction.split(" ",1)

        if not (data in commands):
            sendMsg(msgSocket, "501 Syntax error in parameters or arguments.")
            continue
        if data == "HELP":
            HELP(inputs, msgSocket)
            continue
        elif data == "QUIT":
            sendMsg(msgSocket, "221 Successful Quit.")
            break
        elif data == "USER":
            if loggedIn == True:
                sendMsg(msgSocket, "500 Already logged in.")
                continue
            currentUsername = USER(inputs, msgSocket)
            continue
        elif data == "PASS":
            if loggedIn == True:
                sendMsg(msgSocket, "500 Already logged in.")
                continue
            userID = PASS(inputs, currentUsername, msgSocket)
            if userID == -1:
                currentUsername = ""
            else:
                loggedIn = True
                writeLog("Connection " + str(connectionID) + " is now logged in as : " + currentUsername)
            continue
        elif loggedIn == False:
            sendMsg(msgSocket, "332 Need account for login.")
            continue
        else:
            if data == "LIST":
                LIST(currentDirectory, inputs, msgSocket, fileSocket)
                continue
            elif data == "PWD":
                PWD(inputs, currentDirectory, msgSocket)
                continue
            elif data == "MKD":
                MKD(inputs, currentDirectory, msgSocket, connectionID)
                continue
            elif data == "RMD":
                RMD(inputs, currentDirectory, msgSocket, userID, connectionID)
                continue
            elif data == "CWD":
                currentDirectory = CWD(inputs, currentDirectory, msgSocket)
                continue
            elif data == "DL":
                DL(inputs, currentDirectory, msgSocket, fileSocket, userID)
                if size[userID] < accountingThreshold and alert[userID] and accountingEnable:
                    sendEmail(userID)
                continue
        

    msgSocket.close()
    fileSocket.close()
    print("--user QUITING")

#--------------------------------------------------------------
#--------------------------------------------------------------

def sendEmail(userID):
    writeLog("Sending email to user " + str(userID) + " with email address " + email[userID])
    mailserver = (MAILSERVER, 25)
    clientSocket = socket(AF_INET, SOCK_STREAM)
    clientSocket.connect(mailserver)
    recv = clientSocket.recv(1024)
    recv = recv.decode()
    if recv[:3] != '220':
        print('error in connection request.')
        clientSocket.close()
        return
    
    heloCommand = 'HELO ' + MAILSERVER + '\r\n'
    clientSocket.send(heloCommand.encode())
    recv1 = clientSocket.recv(1024)
    recv1 = recv1.decode()
    if recv1[:3] != '250':
        print('error in HELO.')
        clientSocket.close()
        return
    
    mailFrom = "MAIL FROM:<"+EMAIL+">\r\n"
    clientSocket.send(mailFrom.encode())
    recv2 = clientSocket.recv(1024)
    recv2 = recv2.decode()
    
    if recv2[:3] != '250':
        print('error in MAIL FROM.')
        clientSocket.close()
        return
    
    authLogin = "AUTH LOGIN\r\n"
    clientSocket.send(authLogin.encode())
    recv2 = clientSocket.recv(1024)
    recv2 = recv2.decode()

    if recv2[:3] != '334':
        print('error in AUTH LOGIN.')
        clientSocket.close()
        return
    
    username = b64encode(USERNAME)+"\r\n"
    password = b64encode(PASSWORD)+"\r\n"
    clientSocket.send((username).encode())
    recv2 = clientSocket.recv(1024)
    recv2 = recv2.decode()

    if recv2[:3] != '334':
        print('error in username.')
        clientSocket.close()
        return
    clientSocket.send(password.encode())
    recv2 = clientSocket.recv(1024)
    recv2 = recv2.decode()

    if recv2[:3] != '235':
        print('error in password.')
        clientSocket.close()
        return

    
    rcptTo = "RCPT TO:<" + email[userID] + ">\r\n"
    clientSocket.send(rcptTo.encode())
    recv3 = clientSocket.recv(1024)
    recv3 = recv3.decode()

    if recv3[:3] != '250':
        print('error in RCPT TO.')
        clientSocket.close()
        return
    
    data = "DATA\r\n"
    clientSocket.send(data.encode())
    recv4 = clientSocket.recv(1024)
    recv4 = recv4.decode()

    if recv4[:3] != '354':
        print('error in DATA.')
        clientSocket.close()
        return
    message = "You are running out of download space.\r\n.\r\n"
    clientSocket.send(message.encode())
    recv4 = clientSocket.recv(1024)
    recv4 = recv4.decode()

    if recv4[:3] != '250':
        print('error in message.')
        clientSocket.close()
        return
    writeLog("Email sent to Connection " + str(connectionID) + ".")
    print('email sent.')
    clientSocket.close()
    return

#--------------------------------------------------------------
#--------------------------------------------------------------

def HELP(inputs, msgSocket):
    if len(inputs) != 0:
        sendMsg(msgSocket, "501 Syntax error in parameters or arguments.")
        return

    file = open("etc/help.txt","r") 
    sendMsg(msgSocket, file.read())

#--------------------------------------------------------------
#--------------------------------------------------------------

def QUIT(inputs, msgSocket):
    if len(inputs) != 0:
        sendMsg(msgSocket, "501 Syntax error in parameters or arguments.")
        return
    
    print("--user quiting")
    sendMsg(msgSocket, "221 Successful Quit.")

#--------------------------------------------------------------
#--------------------------------------------------------------

def USER(inputs, msgSocket):
    if len(inputs) == 0:
        sendMsg(msgSocket, "501 Syntax error in parameters or arguments.")
        return ""

    data = inputs[:-1]
    sendMsg(msgSocket, "331 User name okay, need password.")
    return data

#--------------------------------------------------------------
#--------------------------------------------------------------

def PASS(inputs, currentUsername, msgSocket):
    data = inputs[:-1]

    if len(currentUsername) == 0:
        sendMsg(msgSocket, "503 Bad sequence of commands.")
        return -1
    
    for i in range(0, len(user)):
        if user[i] == currentUsername and password[i] == data:
            sendMsg(msgSocket, "230 User logged in, proceed.")
            return i

    sendMsg(msgSocket, "430 Invalid username or password.")
    return -1

#--------------------------------------------------------------
#--------------------------------------------------------------

def LIST(currentDirectory, inputs, msgSocket, fileSocket):
    if len(inputs) != 0:
        sendMsg(msgSocket, "501 Syntax error in parameters or arguments.")
        return

    listOfFiles = ""
    for file in os.listdir(currentDirectory):
        if file[0] != '.' and '.ini' not in file and '.BIN' not in file :
            listOfFiles += file + '\n'
    listOfFiles = listOfFiles[:-1]
    sendMsg(msgSocket, "226 List transfer done.")
    sendMsg(fileSocket, listOfFiles)

#--------------------------------------------------------------
#--------------------------------------------------------------

def PWD(inputs, currentDirectory, msgSocket):
    if len(inputs) != 0:
        sendMsg(msgSocket, "501 Syntax error in parameters or arguments.")
        return
    sendMsg(msgSocket, "257 " + currentDirectory)

#--------------------------------------------------------------
#--------------------------------------------------------------

def CWD(inputs, currentDirectory, msgSocket):
    if len(inputs) == 0 or inputs == " ":
        currentDirectory = DEFAULTDIR
        sendMsg(msgSocket, "250 Successful Change.")
        return currentDirectory
    
    data = inputs[:-1]
    currentDirectoryList = currentDirectory.split("/")
    directoryList = data.split("/")
    for folder in directoryList:
        if folder == '..':
            if len(currentDirectoryList) <= MINDIRLEN:
                sendMsg(msgSocket, "500 Not a valid directory.")
                return currentDirectory
            else:
                currentDirectoryList.pop()
                continue
        elif folder == '.':
            continue
        
        currentDirectoryList.append(folder)
        tempDir = '/'.join(currentDirectoryList)
        if not os.path.exists(tempDir) or os.path.isfile(tempDir):
            sendMsg(msgSocket, "500 Not a valid directory.")
            return currentDirectory
    
    sendMsg(msgSocket, "250 Successful Change.")
    return '/'.join(currentDirectoryList)

#--------------------------------------------------------------
#--------------------------------------------------------------

def MKD(inputs, currentDirectory, msgSocket, connectionID):
    if len(inputs) == 0:
        sendMsg(msgSocket, "501 Syntax error in parameters or arguments.")
        return
    
    flag, createDir = inputs.split(" ",1)
    if flag == "-i":
        if len(createDir) == 0:
            sendMsg(msgSocket, "501 Syntax error in parameters or arguments.")
            return
        createDir = createDir[:-1]
        if '/' in createDir or createDir == '.' or createDir == '..':
            sendMsg(msgSocket, "500 Cannot have '/' in filename or '.' or '..' as filename")
            return
        if os.path.exists(currentDirectory + "/" + createDir):
            sendMsg(msgSocket, "500 Name already exists")
            return
        open(currentDirectory + "/" + createDir, 'w')
        sendMsg(msgSocket, "257 " + createDir + " file created.")
        writeLog("Connection " + str(connectionID) + " created a file at:" + currentDirectory + "/" + createDir )
        return
    
    createDir = inputs[:-1]
    if '/' in createDir or createDir == '.' or createDir == '..':
        sendMsg(msgSocket, "500 Cannot have '/' in filename or '.' or '..' as filename")
        return
    if os.path.exists(currentDirectory + "/" + createDir):
        sendMsg(msgSocket, "500 Name already exists")
        return
    os.makedirs(currentDirectory + "/" + createDir)
    sendMsg(msgSocket, "257 " + createDir + " folder created.")
    writeLog("Connection " + str(connectionID) + " created a folder at:" + currentDirectory + "/" + createDir )

#--------------------------------------------------------------
#--------------------------------------------------------------

def RMD(inputs, currentDirectory, msgSocket, userID, connectionID):
    if len(inputs) == 0:
        sendMsg(msgSocket, "501 Syntax error in parameters or arguments.")
        return
    
    flag, removeDir = inputs.split(" ",1)
    if flag == "-f":
        if len(removeDir) == 0:
            sendMsg(msgSocket, "501 Syntax error in parameters or arguments.")
            return
        removeDir = removeDir[:-1]
        tmpDir = removeDir
        removeDir = currentDirectory + "/" + removeDir
        if not os.path.exists(removeDir):
            sendMsg(msgSocket, "510 Folder does not exist.")
            return

        try:
            shutil.rmtree(removeDir)
            sendMsg(msgSocket, "250 " + tmpDir + " folder deleted.")
            writeLog("Connection " + str(connectionID) + " removed a folder at:" + removeDir )
            return
        except OSError:
            sendMsg(msgSocket, "501 Syntax error in parameters or arguments. Use RMD [filename] to remove a file.")
            return

    removeDir = inputs[:-1]
    tmpDir = removeDir
    removeDir = currentDirectory + "/" + removeDir

    if (not os.path.exists(removeDir)) or (removeDir in authorizationFiles and admin[userID] == 0 and authorizationEnable):
        sendMsg(msgSocket, "550 File unavailable.")
        return
    try:
        os.remove(removeDir)
    except OSError:
        sendMsg(msgSocket, "501 Syntax error in parameters or arguments. Use RMD -f [pathname] to remove a directory.")
        return
    sendMsg(msgSocket, "250 " + tmpDir + " file deleted.")
    writeLog("Connection " + str(connectionID) + " removed a file at:" + removeDir )

#--------------------------------------------------------------
#--------------------------------------------------------------

def DL(inputs, currentDirectory, msgSocket, fileSocket, userID):
    global accountingEnable
    if len(inputs) == 0:
        sendMsg(msgSocket, "501 Syntax error in parameters or arguments.")
        return
    
    filename = inputs[:-1]

    downloadDir = currentDirectory + "/" + filename
    if (not os.path.exists(downloadDir) or (downloadDir in authorizationFiles and admin[userID] == 0 and authorizationEnable)):
        sendMsg(msgSocket, "550 File unavailable.")
        return
    
    try:
        f = open(downloadDir, "rb")
        data = f.read()
        if len(data) > size[userID] and accountingEnable:
            sendMsg(msgSocket, "425 Can't open data connection.")
            return
        writeLog("Connection " + str(connectionID) + " has downloaded the file at:" + downloadDir )  
        sendMsg(msgSocket, "Downloading ...")  
        sendMsg(fileSocket, data)
        sendMsg(msgSocket, "226 Successful Download.")  
        size[userID] -= len(data)
    except IOError:
        sendMsg(msgSocket, "500 Can't download a directory.")    
    return

#--------------------------------------------------------------
#--------------------------------------------------------------

def on_press(key):
    print (key)

#--------------------------------------------------------------
#--------------------------------------------------------------

def sendMsg(msgSocket, message):
    newMessage = ""
    for i in range(0,len(message)):
        newMessage += '0' + message[i]
    newMessage += '1' + '0'
    msgSocket.sendall(newMessage)

#--------------------------------------------------------------
#--------------------------------------------------------------

logging.basicConfig(filename = loggingPath, format='%(relativeCreated)6d %(threadName)s %(message)s')
preprocessUsers()
writeLog("Status: starting")
msgListenSocket = socket(AF_INET, SOCK_STREAM)
msgListenSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
msgListenSocket.bind(("", commandChannelPort))
msgListenSocket.listen(MAXLISTEN)

fileListenSocket = socket(AF_INET, SOCK_STREAM)
fileListenSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
fileListenSocket.bind(("", dataChannelPort))
fileListenSocket.listen(MAXLISTEN)

connectionID = 0

while True:
    try:
        writeLog ("Status: listening")
        msgSocket, address1 = msgListenSocket.accept()
        fileSocket, address = fileListenSocket.accept()
        writeLog ("connection received from:" + str(address[0]) + " msgPORT: " + str(address1[1]) + " filePORT: " + str(address[1]))
        connectionID = connectionID + 1
        writeLog ("creating thread for connection number " + str(connectionID))
        t = threading.Thread(target = handle_client, args = (msgSocket, fileSocket, address, connectionID))
        t.setDaemon(True)
        t.start()
    except KeyboardInterrupt:
        print("got Keyboard interrupt in main Program!")
        msgListenSocket.close()
        fileListenSocket.close()
        sys.exit()