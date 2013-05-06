import SocketServer
import json
import threading
import projectDatabase
import sys
import os
import tempfile

class ClangServer(SocketServer.TCPServer):
  allow_reuse_adress = True

class ClangRequestHandler(SocketServer.BaseRequestHandler):

    projNotFoundData = {'kind':'Error','message':'Project could not be found'}
    def sendProjNotFound(self):
      self.request.sendall(json.dumps(self.projNotFoundData))

    def aquireUnsavedFiles(self,files):
      '''Gets a list of tuples where the first entry is the name of the unsaved file
         and the second a file where the unsaved data is located. Returns a list of tuples
         with the name of unsaved files and the contents of the files'''
      for f in files:
        fh = open(f[1],"r")
        f[1] = fh.read()
        fh.close()
      return files

    def handle_loadfile(self,data):
      '''Load the project for the file and return the files project root'''
      unsavedFiles = self.aquireUnsavedFiles(data['unsavedFiles'])
      projRoot = projectDatabase.filesProjectRoot(data['filename'])
      self.request.sendall(json.dumps({'kind':'result', 'projRoot':projRoot}))
      if projRoot is None:
        return
      loaded = projectDatabase.isProjectLoaded(projRoot)
      projectDatabase.onLoadFile(data['filename'])
      if not loaded:
        print "Project",projRoot,"loaded"

    def handle_closefile(self,data):
      '''Unload the project associate with the file if it is the last file'''
      self.request.sendall(json.dumps({'kind':'result'}))
      projectDatabase.closeFile(data['filename'])

    def handle_dumpsymbols(self,data):
      '''Dumb all symbols in a project'''
      projRoot     = data['projRoot']
      unsavedFiles = self.aquireUnsavedFiles(data['unsavedFiles'])
      proj = projectDatabase.getProjectFromRoot(projRoot)
      if proj is None:
        self.sendProjNotFound()
      else:
        f = tempfile.NamedTemporaryFile(delete = False)
        name = f.name
        f.write('\n'.join('%s,%s,%s' % x for x in proj.getAllTypeNamesInProject()))
        f.close()
        self.request.sendall(json.dumps({'kind':'result','symbols':name}))

    def handle_getusrlocations(self,data):
      '''Get all declarations and defintions of a symbol (given by an usr)'''
      projRoot = data['projRoot']
      unsavedFiles = self.aquireUnsavedFiles(data['unsavedFiles'])
      proj = projectDatabase.getProjectFromRoot(projRoot)
      if proj is None:
        return projNotFoundData
      else:
        self.request.sendall(json.dumps( {'kind':'result','locations':proj.getUsrLocations(data['usr'],data['type'])}))

    def handle_listloadedprojects(self,data):
      self.request.sendall(json.dumps({'kind':'result','projectRoots':projectDatabase.getAllProjects()}))

    def handle(self):
      ''' The main handle function, handles all client requests'''
      try:
        data = json.loads(self.request.recv(1024).strip())
        handle = getattr(self, "handle_" + data["kind"], None)
        if handle is None:
          print "Invalid client request:",data
          self.request.sendall(json.dumps({'kind':'Error','message':'Your request has an invalid or not existing kind'}))
        else:
          handle(data)
      except Exception, e:
        self.request.sendall(json.dumps({'kind':'Error','message':'Internal server error'}))
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print "Unhandled exception while handling request:",e,fname,exc_tb.tb_lineno

        

# the main
def runServer():
  server = ClangServer(("127.0.0.1", 19375), ClangRequestHandler)
  server.serve_forever()

if __name__ == "__main__":
  runServer()
