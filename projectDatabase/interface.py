import clangCompilationDatabase
from projectDatabase import *

def getAllProjects():
  return list(loadedProjects.iterkeys())

def updateProject(projectPath, unsavedFiles):
  loadedProjects[projectPath].updateOutdatedFiles(unsavedFiles)

def searchUpwardForFiles(startPath, fileNames):
  '''Return the first encounter of one of the searched files, upward from the current direcotry'''
  startDir = os.path.abspath(os.path.dirname(startPath))

  curDir  = startDir
  lastDir = ""
  while curDir != lastDir:
    lastDir = curDir
    for f in fileNames:
      if os.path.exists(os.path.join(curDir, f)):
        return curDir #found the file, this is the projects root
      else:
        curDir = os.path.abspath(os.path.join(curDir,os.path.pardir))

  # Nothing found
  return None

def filesProjectRoot(filePath):
  '''Return the root directory for a files project by searching for .clang_complete'''
  return searchUpwardForFiles(filePath, [".clang_complete","compilation_commands.json"])

# global dictonary of all loaded projects
loadedProjects = dict()

def onLoadFile(filePath):
  '''Check if the project for the file already exists. If not, create a new project.
     Add the file to the project.'''
  proj = getOrLoadFilesProject(filePath)
  
  if proj is not None:
    return proj.root
  return None

def onFileSaved(self,path,changedtick,unsavedFiles):
  '''When a file is saved, we want to know so that when the changedtick of the file
     is up to date (meaning the file that is changed is already up to date in the database)
     we want to update the mtime without reparsing it.
     Also of the file is not part of the project (because it did not exist under its file name before)
     we want to add it now.
     '''
  proj = getOrLoadFilesProject(path)
  if proj is not None:
    proj.onFileSaved(path,changedtick,unsaved_files)
  for ex in cppExtensions:
    if path.endswith(ex):
      proj.addFile(path,unsaved_files,unsavedFilesChangedtick)

def getProjectFromRoot(root):
  root = os.path.abspath(root)
  if loadedProjects.has_key(root):
    return loadedProjects[root]
  return None

def getFilesProject(filePath):
  projectRoot = filesProjectRoot(filePath)
  if projectRoot is not None:
    if loadedProjects.has_key(projectRoot):
      return loadedProjects[projectRoot]
  return None

def getOrLoadFilesProject(filePath):
  ''' Returns the project for a file if loaded.
      If not loaded, load it, if that fails, return None.'''
  projectRoot = filesProjectRoot(filePath)
  if projectRoot is None:
    print "Not loading any project, because no root was found"
    return None

  if loadedProjects.has_key(projectRoot):
    return loadedProjects[projectRoot]

  joinedPath1 = os.path.join(projectRoot,"compilation_commands.json")
  joinedPath2 = os.path.join(projectRoot,".clang_complete")
  db = None
  if os.path.exists(joinedPath1):
    db = cindex.CompilationDatabase(joinedPath1)
  else:
    if os.path.exists(joinedPath2):
      db = clangCompilationDatabase.ClangCompilationDatabase(projectRoot)

  if db is None:
    print "Not loading any project, because not compilation database found"
    return None

  dictPath = os.path.join(projectRoot,".clang_complete.project.dict")
  if os.path.exists(dictPath):
    print "Loading clang project dictonary at " + projectRoot
    loadedProjects[projectRoot] = ProjectDatabase.loadProject(projectRoot,db)
    return loadedProjects[projectRoot]
  return None

def getLoadOrCreateFilesProject(filePath):
  ''' Returns the project for a file if loaded.
      If not loaded, load it and return it.'''
  projectRoot = filesProjectRoot(filePath)
  if projectRoot is None:
    print "Not loading any project, because no root was found"
    return None
  joinedPath1 = os.path.join(projectRoot,"compilation_commands.json")
  joinedPath2 = os.path.join(projectRoot,".clang_complete")
  db = None
  if os.path.exists(joinedPath1):
    db = cindex.CompilationDatabase(joinedPath1)
  else:
    if os.path.exists(joinedPath2):
      db = clangCompilationDatabase.ClangCompilationDatabase(projectRoot)

  if db is None:
    print "Not loading any project, because not compilation database found"
    return None

  res = getOrLoadFilesProject(filePath)
  if res is None:
    print "Creating clang project dictonary at " + projectRoot
    loadedProjects[projectRoot] = ProjectDatabase.createProject(projectRoot,db)
    res = loadedProjects[projectRoot]
  return res

def isProjectLoaded(projRoot):
  return loadedProjects.has_key(projRoot)

def onUnloadFile(filePath):
  proj = getFilesProject(filePath)
  if proj is not None:
    proj.closeFile(filePath)
    # should we also update the project here?
    print "Saving clang project dictonary at " + proj.root
    proj.saveProject(os.path.join(proj.root, ".clang_complete.project.dict"));
    del loadedProjects[proj.root]

def getFilesProjectSymbolNames(filePath,args):
  filePath = os.path.normpath(filePath)
  proj = getLoadOrFilesProject(filePath)
  if proj is None:
    print "Sorry, no project for file " + filePath + " found"
  else:
    return proj.getAllTypeNamesInProject()

def getFilesProjectDerivedClassesSymbolNamesForBaseUsr(filePath, args, baseUsr):
  proj = getOrLoadFilesProject(filePath)
  if proj is None:
    print "Sorry, no project for file " + filePath + " found"
  else:
    return proj.getDerivedClassesTypeNames(baseUsr)



conf = cindex.Config()


