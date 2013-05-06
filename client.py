import socket
import json
import menu

def doRequest(data):
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)                           
  print "connecting ..."
  s.connect(('127.0.0.1', 19375))
  print "sending ..."
  s.send(json.dumps(data))
  print "waiting for result ..."
  result = json.loads(s.recv(1024))
  print result
  s.close()

def getAllSymbols():
  root = raw_input("project root> ")
  print "Requesting symbols for project",root
  doRequest({'kind':'dumpsymbols','projRoot':root,'unsavedFiles':{}})

def loadFile():
  name = raw_input("file name> ")
  doRequest({'kind':'loadfile','filename':name,'unsavedFiles':{}})

def listLoadedProjects():
  doRequest({'kind':'listLoadedProjects'})

m = menu.Menu()
m.addItem("Load file",loadFile)
m.addItem("Dump all symbols",getAllSymbols)
m.addItem("List loaded projects",listLoadedProjects)
m.run()
