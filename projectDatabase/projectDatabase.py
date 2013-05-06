import os
import clang.cindex as cindex
import cPickle as pickle
import hashlib

# info about an usr
class UsrInfo:
  ''' Information about an USR located in the database'''
  def __init__(self, usr, kind, displayname, spelling, lexical_parent_usr):
    self.usr = usr
    self.kind = kind
    # files during which parsing this usr was found
    self.associatedFiles = set()
    # location referencing this usr. These are pairs of locations and cursor kinds
    self.references = set()
    # positions where this usr was declared (normaly there should be only one)
    self.declarations = set()
    # positions where this usr is defined
    self.definitions = set()
    if displayname == "":
      self.displayname = spelling
    else:
      self.displayname = displayname
    self.spelling = spelling
    # lexical parent for building full type name
    if (lexical_parent_usr != ""):
      self.lexical_parent = lexical_parent_usr
    else:
      self.lexical_parent = None
    # set if this usr should be listed in a list of all types
    self.shouldBeListed = (self.kind not in [cindex.CursorKind.FIELD_DECL.value,
      cindex.CursorKind.ENUM_CONSTANT_DECL.value,
      cindex.CursorKind.VAR_DECL.value,
      cindex.CursorKind.PARM_DECL.value,
      cindex.CursorKind.TEMPLATE_TYPE_PARAMETER.value,
      cindex.CursorKind.TEMPLATE_NON_TYPE_PARAMETER.value])
    self.isInProject = False

  def removeFile(self,fileName):
    ''' Goes through all information about the usr and remove anything  that has to do wit the file. Returns if the usr has no associated files.'''
    self.references   = set(filter(lambda loc: loc[0] != fileName, self.references))
    self.declarations = set(filter(lambda loc: loc[0] != fileName, self.declarations))
    self.definitions  = set(filter(lambda loc: loc[0] != fileName, self.definitions))
    self.associatedFiles.discard(fileName)
    return len(self.associatedFiles) == 0

  def addDefinition(self,loc,projRoot):
    addition = (os.path.normpath(loc.file.name), loc.line, loc.column)
    if addition not in self.definitions:
      self.definitions.add(addition)
      if not self.isInProject:
        if addition[0].startswith(projRoot):
          self.isInProject = True

  def addDeclaration(self,loc,projRoot):
    self.declarations.add((os.path.normpath(loc.file.name), loc.line, loc.column))
    addition = (os.path.normpath(loc.file.name), loc.line, loc.column)
    if addition not in self.declarations:
      self.declarations.add(addition)
      if not self.isInProject:
        if addition[0].startswith(projRoot):
          self.isInProject = True

  def addReference(self,loc,kind,parent = None,projRoot = None):
    ''' From the parent we can get the type of the derived class in
        case of a CXX_BASE_SPECIFIER.'''
    self.references.add((os.path.normpath(loc.file.name), loc.line, loc.column, kind, parent))

  def addAssociatedFile(self,fileName):
    self.associatedFiles.add(os.path.normpath(fileName))

  def getLocations(self, locType):
    ''' Get the locations, sorted!'''
    if locType == "declarations":
      res = list(self.declarations)
      res.sort()
      return res
    if locType == "definitions":
      res = list(self.definitions)
      res.sort()
      return res
    if locType == "references":
      res = list(set(map(lambda x: (x[0],x[1],x[2]), self.references)))
      res.sort()
      return res
    if locType == "declarations_and_definitions":
      decl = self.getLocations("declarations")
      defi = self.getLocations("definitions")
      decl.extend(defi)
      return decl
    if locType == "occurences":
      res = list(self.declarations.union(self.definitions))
      res.extend(self.getLocations("references"))
      res.sort()
      return res

  def setTemplate(self,templUsr):
    ''' Set the template parameter. We set this only for types (not i.E. variables)
        derived from a template. Things that are derived from template should also not
        be listed!!!.'''
    self.template = templUsr
    if self.kind in [cindex.CursorKind.CLASS_DECL.value,
        cindex.CursorKind.FUNCTION_DECL.value]:
      self.shouldBeListed = False

class FileInfo():
  '''Information about a file located in a projects database'''
  def __init__(self, fileName, args = None):
    self.name = fileName
    # set usrs this references
    self.usrStrings = set()
    self.args = args
    # diagnostics for the file
    self.diagnostics = set()

  def parseDiagnostics(self, diagnostics):
    self.diagnostics = set()
    for d in diagnostics:
      if d.location.file:
        filename = d.location.file.name
      else:
        filename = ""
      # get the type
      if d.severity == d.Ignored:
        type = 'I'
      elif d.severity == d.Note:
        type = 'I'
      elif d.severity == d.Warning:
        if "argument unused during compilation" in d.spelling:
          continue
        type = 'W'
      elif d.severity == d.Error:
        type = 'E'
      elif d.severity == d.Fatal:
        type = 'E'
      else:
        continue
      self.diagnostics.add((filename, d.location.line, d.location.column, d.spelling + " (while parsing " + os.path.basename(self.name) + ")" , type, d.severity))

class IncludedFile():
  ''' A file on which other depend (meaning with
      this file changes, the other has to be recompiled)'''
  def __init__(self,hashval):
    self.dependedFiles = set()
    self.hashval = hashval

  def addDependendFile(self,path,md5):
    self.dependedFiles.add((os.path.normpath(path), md5))

  def removeDependendFile(self,path):
    path = os.path.normpath(path)
    if path in self.dependedFiles:
      self.dependedFiles.remove(path)
    return len(self.dependedFiles) == 0


class ProjectDatabase:
  ''' Database for all files of a project.'''
  def __init__(self, root, compDb):
    # files in the project and the corresponing FileInfo
    self.fileInfos = dict()
    # file that are included from somewhere
    self.includedFiles = dict()
    # USRs in this project and the corresponding UsrInfo
    self.usrInfos = dict()
    self.compilationDatabase = compDb
    self.root = root

  @staticmethod
  def createProject(rootPath,db):
    res = ProjectDatabase(rootPath,db)
    res.updateOutdatedFiles([])
    res.saveProject()
    return res

  @staticmethod
  def loadProject(rootPath,db):
    f = open(os.path.join(rootPath,".clang_complete.project.dict"),"r")
    res = pickle.load(f)
    f.close()
    res.compilationDatabase = db
    res.updateOutdatedFiles([])
    if isinstance(res,ProjectDatabase):
      return res
    else:
      raise RuntimeError(dictPath + " is not a saved project database")

  def getAllDiagnostics(self):
    res = set()
    for p,f in self.fileInfos.iteritems():
      res = res.union(f.diagnostics)
    return res

  def saveProject(self):
    dictPath = os.path.join(self.root,".clang_complete.project.dict")
    f = open(dictPath,"w")
    pickle.dump(self,f,protocol=2)
    f.close()

  def addFile(self,fileName, unsavedFiles):
    ''' Add a file to database'''
    # check if file is already known
    if (self.fileInfos.has_key(fileName)):
      return
    print "Parsing",fileName
    
    # create libclang compatible data structure
    transUnit = cindex.TranslationUnit.from_source(fileName, args = self.compilationDatabase.getCompileCommands(fileName), unsaved_files = unsavedFiles)

    cursor = transUnit.cursor
    # remember file
    self.fileInfos[fileName] = FileInfo(fileName, self.compilationDatabase.getCompileCommands(fileName))
    fileInfo = self.fileInfos[fileName]
    fileInfo.parseDiagnostics(transUnit.diagnostics)
    # build database with file
    self.buildDatabase(cursor,None,fileInfo,fileName)

    # build include dependency
    unsaved_files = dict(unsavedFiles)
    for i in transUnit.get_includes():
      name = os.path.normpath(i.source.name)
      if name in unsavedFiles:
        md5 = hashlib.md5(unsafedFiles[name]).hexdigest()
      else:
        f = open(name,'r')
        md5 = hashlib.md5(f.read()).hexdigest()
        f.close()
      if name not in self.includedFiles:
        self.includedFiles[name] = IncludedFile(md5)
      self.includedFiles[name].addDependendFile(fileName,md5)

  def removeFile(self,fileName):
    ''' Remove a file from the database.
        Removes all references from USRs to this file
        and removes USRs that do not reference any files anyore'''
    fileInfo = self.fileInfos[fileName]
    for u in fileInfo.usrStrings:
      if self.usrInfos[u].removeFile(fileName):
        # true means the USR is not referenced anymore
        del self.usrInfos[u]
   
    for i in self.includedFiles.itervalues():
      i.removeDependendFile(fileName)

    del self.fileInfos[fileName]

  def updateOrAddFile(self,fileName, unsavedFiles):
    ''' Remove (if it exits) and re-add a file'''
    if self.fileInfos.has_key(fileName):
      self.removeFile(fileName)
    self.addFile(fileName, unsavedFiles)

  def updateOutdatedFiles(self, unsavedFiles):
    ''' Search for files which md5 has changed
        and update those.
        Also update all files for which the args are different than the given ones.
        Also remove files not existing anymore.'''

    unsavedFilesDict = dict(unsavedFiles)

    outdatedFiles = set()
    for name,includedFile in self.includedFiles.iteritems():
      if not os.path.exists(name):
        outdatedFiles = outdatedFiles.union(includedFile.dependedFiles)
        continue
      if name in unsavedFiles:
        md5 = hashlib.md5(unsavedFilesDict[name]).hexdigest()
      else:
        f = open(name,"r")
        md5 = hashlib.md5(f.read()).hexdigest()
        f.close()

      if md5 != includedFile.hashval:
        outdatedFiles = outdatedFiles.union(includedFile.dependedFiles)
        # we will update, so update md5
        includedFile.md5 = md5
        continue

    for f in self.fileInfos.itervalues():
      if f.args != self.compilationDatabase.getCompileCommands(f.name):
        outdatedFiles.add(f.name)

    for f in outdatedFiles:
      if os.path.exists(f):
        self.updateOrAddFile(f, unsavedFiles)
      else:
        self.removeFile(f)

    for f in self.compilationDatabase.getAllFiles():
      if not self.fileInfos.has_key(f):
        self.addFile(f,unsavedFiles)

  def uninterestingCursor(self,c):
    ''' Return true of the type of the cursor does not go into out database'''
    return c.kind.value in [cindex.CursorKind.CXX_ACCESS_SPEC_DECL.value,
        cindex.CursorKind.LINKAGE_SPEC.value,
        cindex.CursorKind.UNEXPOSED_DECL.value]

  def getLexicalParent(self,cursor):
    '''helper function to get the lexical parent'''
    if cursor.lexical_parent is None:
      return None
    else:
      return cursor.lexical_parent.get_usr()

  # helper function adding declaration and returning the corresponding usr
  def addDeclaration(self,cursor, usrFileEntry, fileName):
    # if the lexical parent is delcaration, than also add it
    if (cursor.lexical_parent is not None) and cursor.lexical_parent.kind.is_declaration() and not self.uninterestingCursor(cursor.lexical_parent):
      self.addDeclaration(cursor.lexical_parent, usrFileEntry, fileName)
    usrInfo = self.getOrCreateUsr(cursor.get_usr(), cursor.kind.value, usrFileEntry, cursor.displayname, cursor.spelling, self.getLexicalParent(cursor))
    # check if this is template
    if cursor.template is not None and cursor.template != conf.lib.clang_getNullCursor():
      usrInfo.setTemplate(cursor.template.get_usr())

    if cursor.is_definition():
      usrInfo.addDefinition(cursor.location,self.root)
    else:
      usrInfo.addDeclaration(cursor.location, self.root)
    usrInfo.addAssociatedFile(fileName)
    return usrInfo

  def readCursor(self,c,parent, usrFileEntry, fileName):
    ''' Read symbol at cursor position.
        Also read any symbol cursor references
        and their lexical parents.
    '''
    if self.uninterestingCursor(c):
      return

    # get the usr of the parent
    # this is interesting for CXX_BASE_SPECIFIER, becaue we can get the type of the
    # derived class this way
    if parent is not None:
      parentUsr = parent.get_usr()
    else:
      parentUsr = None
    # get anything we are referencing
    ref = None
    if (not (c.referenced is None)) and (c.referenced != conf.lib.clang_getNullCursor()):
      ref = c.referenced
    # we have no interest in a cursor with no location in a source file
    # also if it nor its reference has an non-empty usr, it has nothing
    # interesing in it
    if c.location.file == None:
      return
    if c.get_usr() == "" and (ref is None or ref.get_usr() == ""):
      return

    # if we have a reference, add it
    if not (ref is None):
      if not ref.kind.is_declaration():
        raise RuntimeError("Reference has to be delcaration")
      if self.uninterestingCursor(ref):
        return
      refUsrInfo = self.addDeclaration(ref, usrFileEntry, fileName)

    # add the curser itself
    # declarations or  ...
    if c.kind.is_declaration():
      self.addDeclaration(c, usrFileEntry,fileName)

    # reference
    if c.kind.is_reference():
      if ref is None:
        raise RuntimeError("Reference without reference cursor")
      refUsrInfo.addReference(c.location, c.kind.value, parentUsr)

    # expression
    if c.kind.is_expression():
      # expression without references do not interest us
      if not (ref is None):
        refUsrInfo.addReference(c.location, c.kind.value, parentUsr)

  def buildDatabase(self,c,parent, usrFileEntry, fileName):
    ''' Build (extend) the database based on a cursors.
        Calls readCursor and recurse'''
    # if we are outside of the project
    # we are not interested. We are only interested in things defined, declared or referenced in a file part of the project
    # and since we parse all files, we can be sure not to miss anything
    # if we do stop when not in the source file, database building takes much longer
    if not (c.location.file is None) and not c.location.file.name.startswith(self.root):
      return
    self.readCursor(c,parent, usrFileEntry, fileName)

    for child in c.get_children():
      self.buildDatabase(child, c, usrFileEntry, fileName)

  def getOrCreateUsr(self,usr,kind,usrFileEntry,displayname,spelling,lexical_parent_usr):
    '''If the USR does not yet exist, create it.
       In any case, return it.'''
    usrFileEntry.usrStrings.add(usr)
    if not (self.usrInfos.has_key(usr)):
      self.usrInfos[usr] = UsrInfo(usr, kind, displayname, spelling, lexical_parent_usr)
    return self.usrInfos[usr]

  def getFullTypeNameFromUsr(self,usrName):
    '''Get the full type name from an usr string'''
    if self.usrInfos.has_key(usrName):
      return self.getFullTypeName(self.usrInfos[usrName])
    else:
      return "<not found usr: " + usrName + ">"

  def getFullTypeName(self,usrInfo):
    '''Get thhe full type name from an UsrInfo object.'''
    if not (usrInfo.lexical_parent is None):
      return self.getFullTypeNameFromUsr(usrInfo.lexical_parent) + "::" + usrInfo.spelling
    else:
      return usrInfo.spelling

  def getFullDisplayTypeName(self,usrInfo):
    '''Get the full type name, with the top level beeing the display name.'''
    if not (usrInfo.lexical_parent is None):
      return self.getFullTypeNameFromUsr(usrInfo.lexical_parent) + "::" + usrInfo.displayname
    else:
      return usrInfo.displayname

  def getUsrLocations(self, usr, locType):
    if not self.usrInfos.has_key(usr):
      print "Usr not found:",usr
      return []
    return self.usrInfos[usr].getLocations(locType)

  def getUsrSpelling(self,usr):
    return self.usrInfos[usr].spelling

  def getAllTypeNames(self):
    '''List of all (full) type names and the position where
       they are declated. If multiple positions are found for, the type name
       is returned multiple times.
       Returns a list of typles:
       [(typeName,set([(fileName,line,column)...]),kindname,usr),...]
       '''
    res = []
    for k,usr in self.usrInfos.iteritems():
      if not usr.shouldBeListed:
        continue
      tName = self.getFullDisplayTypeName(usr)
      kind  = cindex.CursorKind.from_id(usr.kind).name
      # add the declaration positions. If there are none, add definition positions
      res.append( (tName,kind,usr.usr) )
    res.sort()
    return res

  def getAllTypeNamesInProject(self):
    ''' same as getAllTypeNames, but reduced to files in the project
       Returns a list of typles:
       [(typeName,set([(fileName,line,column)...]),kindname,usr),...]'''
    res = []
    for k,usr in self.usrInfos.iteritems():
      if not usr.shouldBeListed or not usr.isInProject:
        continue
      tName = self.getFullDisplayTypeName(usr)
      kind  = cindex.CursorKind.from_id(usr.kind).name
      # add the declaration positions. If there are none, add definition positions
      res.append( (tName,kind,usr.usr) )
    res.sort()
    return res

  def getDerivedClassesTypeNames(self, baseUsr):
    '''Iterator for type name of classes derived from the class specified by the usr
       Returns a list of tuples:
       [(typename,(fileName,line,column))]'''
    if not self.usrInfos.has_key(baseUsr):
      print "Sorry, base class not found"
    else:
      for file,row,column,kind,parentUsr in self.usrInfos[baseUsr].references:
        if kind == cindex.CursorKind.CXX_BASE_SPECIFIER.value:
          if (parentUsr is None) or (not self.usrInfos.has_key(parentUsr)):
            print "Sorry, no usr for derived class of ",baseUsr
          else:
            baseUsrInfo = self.usrInfos[parentUsr]
            positions = baseUsrInfo.definitions
            baseName = self.getFullTypeName(baseUsrInfo)
            for p in positions:
              yield (baseName,p)

  def getTemplateUsrSubRenameLocations(self, usrInfo):
    # gather occurences of all usrInfos whose template parameter points to us
    subOccurences = []
    for ui in self.usrInfos.itervalues():
      if hasattr(ui,'template') and ui.template == usrInfo.usr:
        #subOccurences.extend(ui.getLocations("occurences"))
        subOccurences.extend(self.getUsrSubRenameLocations(ui))
    # constructor, destructor and stuff is the same as for class declaration
    subOccurences.extend(self.getClassDeclUsrSubRenameLocations(usrInfo))
    # unite and remove dublicate candidates
    return list(set(subOccurences))

  def getClassDeclUsrSubRenameLocations(self, usrInfo):
    # if it is a class, we need to add constructor and destructor
    constrAndDestOcc = []
    for ui in self.usrInfos.itervalues():
      if ui.kind in [cindex.CursorKind.CONSTRUCTOR.value,cindex.CursorKind.DESTRUCTOR.value] and ui.lexical_parent == usrInfo.usr:
        constrAndDestOcc.extend(self.getUsrSubRenameLocations(ui))
    # unite and remove duplicate candidates
    return list(set(usrInfo.getLocations("occurences")).union(set(constrAndDestOcc)))

  def getDestructorUsrSubRenameLocations(selgf,usrInfo):
    # actually, it is just the occurences. But added one to all columns
    return map(lambda l: (l[0],l[1],l[2]+1),usrInfo.getLocations("occurences"))

  def getUsrSubRenameLocations(self, usrInfo):
    '''Get all name locations which are "below" this one. In difference to
       getRenameLocations, this function does not look into parents (like self.tempate)'''
    # if we are a template, get our rename locations + all of our instatiations
    if usrInfo.kind in [cindex.CursorKind.CLASS_TEMPLATE.value,
                        cindex.CursorKind.FUNCTION_TEMPLATE.value]:
      return self.getTemplateUsrSubRenameLocations(usrInfo)

    if usrInfo.kind == cindex.CursorKind.CLASS_DECL.value:
      return self.getClassDeclUsrSubRenameLocations(usrInfo)

    if usrInfo.kind == cindex.CursorKind.DESTRUCTOR.value:
      return self.getDestructorUsrSubRenameLocations(usrInfo)

    # default behavior is to return simple all occurences
    return usrInfo.getLocations("occurences")

  def getUsrRenameLocations(self, usr):
    '''Return all locations where the name would have to be exchanged when the usr is renamed.
       Queries the rename locations from "parents" (like self.template) or returns the output
       of getUsrSubRenameLocations'''
    # extract the usrInfo
    usrInfo = self.usrInfos[usr]

    if hasattr(usrInfo,'template'):
      return self.getUsrRenameLocations(usrInfo.template)

    # some kinds need to return the rename locations of the lexical parent
    if usrInfo.kind in [cindex.CursorKind.CONSTRUCTOR.value,
                        cindex.CursorKind.DESTRUCTOR.value]:
      return self.getUsrRenameLocations(usrInfo.lexical_parent)

    #default: return sub locations
    return self.getUsrSubRenameLocations(usrInfo)


cppExtensions = [".cpp",".cc"]

conf = cindex.Config()

