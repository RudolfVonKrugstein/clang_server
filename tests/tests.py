import sys
sys.path.append("..")

import server
import client
import threading
import os
import socket
import json
import random

class TestBasics:

  def doClientRequest(self,data):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', self.serverPort))
    s.send(json.dumps(data))
    result = json.loads(s.recv(1024))
    s.shutdown(1)
    s.close()
    return result

  def setUp(self):
    print "Starting server ..."
    self.serverPort = random.randrange(10000,15000)
    self.server = server.ClangServer(("127.0.0.1",self.serverPort), server.ClangRequestHandler)
    self.serverThread = threading.Thread(target = self.server.serve_forever)
    self.serverThread.start()

  def tearDown(self):
    print "Stoping server ..."
    self.server.shutdown()
    print "Joining thread ..."
    self.serverThread.join()

  def testLoadFile(self):
    fileName = os.path.abspath("./projects/test1/main.cpp")
    res = self.doClientRequest({'kind':'loadfile','filename':fileName,'unsavedFiles':{}})
    assert res['kind'] == 'result'
    assert res['projRoot'] == os.path.dirname(fileName)

  def testListProjects(self):
    # load the file, so that the project may be there
    self.testLoadFile()
    res = self.doClientRequest({'kind':'listloadedprojects'})
    assert res['kind'] == 'result'
    assert res['projectRoots'] == [os.path.abspath("./projects/test1")]

  def testDumpSymbols(self):
    # load the file, so that the project may be there
    self.testLoadFile()
    projRoot = os.path.abspath("./projects/test1")
    res = self.doClientRequest({'kind':'dumpsymbols','projRoot':projRoot,'unsavedFiles':{}})
    assert res['kind'] == 'result'
    assert os.path.exists(res['symbols'])

  def testGetDeclarationsAndDefintions(self):
    # load the file, so that the project may be there
    self.testLoadFile()
    projRoot = os.path.abspath("./projects/test1")
    res = self.doClientRequest({'kind':'getusrlocations','projRoot':projRoot,'usr':'c:@F@main','type':'declarations_and_definitions','unsavedFiles':{}})
    assert res['kind'] == 'result'
    assert res['locations'] == [[os.path.join(projRoot,"main.cpp"), 1, 5]]

  def testGetRenameLocations(self):
    # load the file, so that the project may be there
    self.testLoadFile()
    projRoot = os.path.abspath("./projects/test1")
    res = self.doClientRequest({'kind':'getusrlocations','projRoot':projRoot,'usr':'c:@F@main','type':'rename','unsavedFiles':{}})
    assert res['kind'] == 'result'
    assert res['locations'] == [[os.path.join(projRoot,"main.cpp"), 1, 5]]


