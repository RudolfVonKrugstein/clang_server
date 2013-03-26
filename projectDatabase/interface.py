from projectDatabase import *

def updateProject(projectPath, unsavedFiles):
  loadedProjects[projectPath].updateOutdatedFiles(unsavedFiles)

def searchUpwardForFile(startPath, fileName):
  '''Return the first encounter of the searched file, upward from the current direcotry'''
  startDir = os.path.abspath(os.path.dirname(startPath))

  curDir  = startDir
  lastDir = ""
  while curDir != lastDir:
    lastDir = curDir
    if os.path.exists(os.path.join(curDir, fileName)):
      return curDir #found the file, this is the projects root
    else:
      curDir = os.path.abspath(os.path.join(curDir,os.path.pardir))

  # Nothing found
  return None

def filesProjectRoot(filePath):
  '''Return the root directory for a files project by searching for .clang_complete'''
  return searchUpwardForFile(filePath, ".clang_complete.project.dict")

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

def getFilesProjRoot(filePath):
  return filesProjectRoot(filePath)

def getFilesProject(filePath):
  projectRoot = filesProjectRoot(filePath)
  if projectRoot is not None:
    if loadedProjects.has_key(projectRoot):
      return loadedProjects[projectRoot]
  return None

def getOrLoadFilesProject(filePath):
  ''' Returns the project for a file if loaded.
      If not loaded, load it and return it.'''
  projectRoot = filesProjectRoot(filePath)
  if projectRoot is None:
    return None
  joinedPath = os.path.join(projectRoot,".clang_complete")
  if os.path.exists(joinedPath):
    f = open(joinedPath,"r")
    args = f.readlines()
    f.close()
  else:
    args = []

  if projectRoot is not None:
    if not loadedProjects.has_key(projectRoot):
      print "Loading clang project dictonary at " + projectRoot
      loadedProjects[projectRoot] = ProjectDatabase.loadProject(os.path.join(projectRoot, ".clang_complete.project.dict"))
      loadedProjects[projectRoot].args = args
    return loadedProjects[projectRoot]
  return None


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

def createOrUpdateProjectForFile(path,args, unsavedFiles):
  '''Create a project for the file, by searching for .clang_complete
     and creating the project there'''
  projectPath = searchUpwardForFile(path,".clang_complete")
  if projectPath is None:
    print "Cannot create project because I cannot find .clang_complete"
    return None
  proj = getOrLoadFilesProject(path)
  if proj is None:
    proj = ProjectDatabase(projectPath,args)
    for f in find_cpp_files(projectPath):
      proj.addFile(f,unsavedFiles)
    loadedProjects[projectPath] = proj
  else:
    proj.args = args
    proj.updateOutdatedFiles(unsavedFiles)
  proj.saveProject(os.path.join(projectPath, ".clang_complete.project.dict"))
  return projectPath

def getFilesProjectSymbolNames(filePath,args):
  filePath = os.path.normpath(filePath)
  proj = getOrLoadFilesProject(filePath)
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

def find_files(directory, patterns):
  ''' Supporting function to iterate over all files
  recusivly in a directory which follow a specific pattern.'''
  for root, dirs, files in os.walk(directory):
    for basename in files:
      for pattern in patterns:
        if fnmatch.fnmatch(basename, pattern):
          filename = os.path.join(root, basename)
          yield filename

def find_cpp_files(path = "."):
  '''Iterate over all files which are cpp file'''
  return find_files(path,map (lambda ex: "*" + ex, cppExtensions))

cppExtensions = [".cpp",".cc"]

conf = cindex.Config()


