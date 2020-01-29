# -*- coding: utf-8 -*-
from matplotlib.pyplot import *
import matplotlib.pyplot as plt
from IPython.display import HTML, Image, clear_output
import ipywidgets as widgets
import requests
import urllib.request
import csv
import codecs
import pandas as pd
import re
import json
import yaml
import os
import datetime
import shutil


def natural_sort(l):
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)


class Citableloader(object):
    """
    Load resource via a DOI which points to a Citable:
      call this function:

        - resource = Citableloader(DOI)  #for a single DOI

      apply different methods on the resource (resource.func()):
        - resource.metadata()  #the corresponding metadata
        - resource.json() #load json file
        - resource.df() #load json file as pandas dataframe
        - resource.debook() # load pdf with interactive tool 'dEbook-Viewer'
        - resource.pdf() # load PDF with standard viewer
        - resource.imageshow() # load image and show
        - resource.imagesave() # save image in local folder
        - resource.csv() # load csv file
        - resource.collection() # load overview json (each collections has its own overview json)
        - resource.docu() # a short introduction of collection & citable
        - resource.landingpage() # shows to the landing page of DOI
        - resource.filename() # returns file name
        - resource.datatype() # returns type of data (e.g. jpg or pdf)
        - resource.resource() # returns all digital resources including DOI
        - resource.getdoi() # returns DOI

      example:
        - single DOI:
          r=Citableloader('10.17171/1-3-388-1')
          r.filename()

    """
    def __init__(self, doi, types, project):
        self.doVerify = True
        if types == "doi":
            self.url = 'https://dx.doi.org/'+doi
            self.response0 = requests.get(self.url, verify=self.doVerify)
            if self.response0.url.split('//')[0] == 'http:':
                self.landingpage_url = re.sub('CitableHandler', 'collection', re.sub('http', 'https', self.response0.url))
        if types == "et":
            collection = re.findall('[A-Z]{4}|[A-Z]{3}', doi)[0]
            number = re.sub(collection, '', doi)
            if '/' in number:
                self.url = 'https://repository.edition-topoi.org/CitableHandler/' + collection + '/single/' + number
            else:
                self.url = 'https://repository.edition-topoi.org/CitableHandler/' + collection + '/single/' + number + '/0'
            self.landingpage_url = re.sub('CitableHandler', 'collection', self.url)
            self.response0 = requests.get(self.url, verify=self.doVerify)
        if types == "dev":
            collection = re.findall('[A-Z]{4}|[A-Z]{3}', doi)[0]
            number = re.sub(collection, '', doi)
            if '/' in number:
                self.url = 'http://repositorytest.ancient-astronomy.org/CitableHandler/' + collection + '/single/' + number
            else:
                self.url = 'http://repositorytest.ancient-astronomy.org/CitableHandler/' + collection + '/single/' + number + '/0'
            self.landingpage_url = re.sub('CitableHandler', 'collection', self.url)
            self.response0 = requests.get(self.url, verify=self.doVerify)
        if types == 'local':
            self.project = project
            if self.project is False:
                print("Please set project='NAME' parameter, trying to guess data path and project name...")
                self.dataPath = '..' + os.sep + 'data'
                self.project = os.getcwd().split(os.sep)[-3]
            else:
                self.docPath = os.path.join(os.path.expanduser('~'), 'ResearchCloud','Documentation')
                #self.docPath = os.path.expanduser('~') + '/ResearchCloud/Documentation'
                try:
                    with open('{0}/{1}.yml'.format(self.docPath, self.project)) as file:
                        doc = yaml.load(file)
                    self.dataPath = os.path.expanduser(doc['dataFolder'])
                except FileNotFoundError as error:
                    print("Could not read 'dataFolder' key in project {0}.yml file in {1}. Does it exist?".format(self.project, self.docPath))
                    raise
            parts = doi.split('.')[0].split('_')
            if len(parts) > 2:
                name = '_'.join(parts[:-1])
            elif len(parts) > 1:
                name = '_'.join(parts)
            else:
                name = parts[0]
            self.name = name
            versions = [doi]
            for file in os.listdir(self.dataPath):
                if file.startswith(self.name + '_v'):
                    versions.append(file)
            self.versions = [x for x in versions if not ('_metadata' in x or '_documentation' in x)]
            if len(self.versions) > 1:
                latest = natural_sort(self.versions)[-1]
                print('File version {0}'.format(latest))
            else:
                latest = doi
            self.path = self.dataPath + '/' + latest
            self.metadataPath = self.dataPath + '/' + self.name + '_metadata.json'
            self.documentationPath = self.dataPath + '/' + self.name + '_documentation.json'
            self.local = True

        if types in ['doi', 'et', 'dev']:
            self.local = False
            # Online data formats
            self.data = requests.get(self.response0.url + '?getDigitalFormat', verify=self.doVerify)
            self.alternatives = requests.get(self.response0.url + '?getAlternatives', verify=self.doVerify)
            self.alternativefile = requests.get(self.response0.url + '?getAlternativeFile', verify=self.doVerify)
            self.doi = doi
            r = self.response0.url
            try:
                r = r.split("https://repository.edition-topoi.org/")[1]
            except:
                if types in ['doi', 'et']:
                    r = r.split("http://repository.edition-topoi.org/")[1]
                elif types == 'dev':
                    r = r.split("http://repositorytest.ancient-astronomy.org/")[1]
            r = r.split('/')
            try:
                self.d = re.findall("filename=(.+)", self.data.headers['Content-disposition'])[0].replace('\"', '')
                if types in ['doi', 'et']:
                    self.link = "http://repository.edition-topoi.org/"+r[1]+'/Repos'+r[1]+'/'+r[1]+r[3]+'/'+self.d
                elif types == 'dev':
                    self.link = "http://repositorytest.ancient-astronomy.org/"+r[1]+'/Repos'+r[1]+'/'+r[1]+r[3]+'/'+self.d
            except:
                pass

    ######
    ##
    #  Write local data in citable compatible format
    ##
    #####

    def write(self, data, newVersion=False):
        """Write citable-formated data in local directory."""
        if not self.local:
            raise ValueError("Can only write local files.")
        try:
            if not os.path.exists(self.dataPath):
                os.makedirs(self.dataPath)
            try:
                if newVersion:
                    file = open(self.path, 'r')
                    print('File exist, increasing version...')
                    parts = re.split('([0-9]+)', self.path)
                    if len(parts) > 2:
                        if parts[-3].endswith('_v'):
                            parts[-2] = int(parts[-2])
                            parts[-2] += 1
                            parts[-2] = str(parts[-2])
                        else:
                            parts[-2] + '_v1'
                        fileVersion = ''.join(parts)
                    else:
                        partsLess = self.path.split('.')
                        partsLess[-1] = '_v1.' + partsLess[-1]
                        fileVersion = '.'.join(partsLess[:-1]) + partsLess[-1]
                    self.path = fileVersion
                else:
                    fileVersion = self.path
            except FileNotFoundError:
                file = open(self.path, 'w')
                fileVersion = self.path

            if type(data) == pd.core.frame.DataFrame:
                data.to_json(fileVersion, orient='table')
            else:
                with open(fileVersion) as file:
                    file.write(data)

            try:
                file = open(self.metadataPath, 'r')
            except:
                useExisting = input('Use existing metadata? (y/N):')
                if useExisting == 'y':
                    path = input('Enter filename:')
                    shutil.copy2(self.dataPath + os.sep + path, self.metadataPath)
                else:
                    now = datetime.datetime.now()
                    # print('Please add metadata:')
                    creators = input('Creators:')
                    title = input('Title:')
                    metaDict = {'Creators': creators, 'Title': title,
                                'Date':  now.strftime("%d. %b. %Y"), 'Publisher': 'Edition Topoi',
                                'Subtitle': '', 'Abstract': '', 'Description': '',
                                'Further Information': '', 'Research Group': '',
                                'Contributor Name': '', 'Contributor Type': '',
                                'Institutions': '', 'Holder Digital Source': '',
                                'Research Types': '', 'Format': type(data).__name__,
                                'Language Source/Project': '', 'Geolocation/Region': '',
                                'Subject': '', 'Keywords': '', 'Other': '',
                                'CC Licence': 'CC BY-NC-SA 3.0: Attribution - NonCommercial - ShareAlike'}
                    json.dump(metaDict, open(self.metadataPath, 'w'))
                    print('Wrote metadata file {0}'.format(self.metadataPath))

            try:
                file = open(self.documentationPath, 'r')
            except:
                # print('Please add documentation:')
                useExisting = input('Use existing documentation? (y/N):')
                if useExisting == 'y':
                    path = input('Enter filename:')
                    shutil.copy2(self.dataPath + os.sep + path, self.documentationPath)
                else:
                    try:
                        docDict = {}
                        for key in data.keys():
                            inKey = input(key + ':')
                            docDict[key] = inKey
                    except:
                        docDict = {}
                        inKey = input('Description:')
                        docDict['Description'] = inKey
                    json.dump(docDict, open(self.documentationPath, 'w'))
                    print('Wrote documentation file {0}'.format(self.documentationPath))
        except:
            raise IOError("Could not write file.")

    ######
    ##
    #  General metadata functions
    ##
    #####

    def documentation(self):
        """Returns the documentation for database objects."""
        if self.local:
            try:
                with open(self.documentationPath) as file:
                    data = file.read()
                    jsonData = json.loads(data)
                infoList = []
                for fstLevelKey in jsonData.keys():
                    val = jsonData[fstLevelKey]
                    if val != '':
                        infoList.append((fstLevelKey, val))
                df = pd.DataFrame(infoList)\
                    .rename(columns={0: 'Value', 1: 'Description'})
                style = df.style\
                    .set_table_styles([{'selector': 'th', 'props': [('text-align', 'left')]}])\
                    .set_properties(**{'text-align': 'left'})
                return style
            except:
                print("Found no documentation file at {0}.".format(self.documentationPath))

        try:
            res = requests.get(re.sub('/\d$', '/1', self.url) + '?getDigitalFormat')
            df = pd.DataFrame([res.json()]).transpose()\
                .reset_index().rename(columns={'index': 'Value', 0: 'Description'})
            style = df.style\
                .set_table_styles([{'selector': 'th', 'props': [('text-align', 'left')]}])\
                .set_properties(**{'text-align': 'left'})
            return style
        except:
            print("No documentation available. Please try .metadata()")

    def status(self):
        """Publication status"""
        obj = requests.get(self.response0.url + '?getDigitalFormats', verify=self.doVerify).json()
        if 'status' in obj.keys():
            print(obj['status'])
            return
        try:
            res = {
                "Object": obj["General Information"]["Identifier"],
                "Status": obj["General Information"]["Status"],
                "Version": obj["General Information"]["Dev-Version"]
                }
            return res
        except:
            print("digital resource has publication status")

    def metadata(self):
        if self.local:
            try:
                with open(self.metadataPath) as file:
                    data = file.read()
                    jsonData = json.loads(data)
                infoList = []
                for fstLevelKey in jsonData.keys():
                    val = jsonData[fstLevelKey]
                    if val != '':
                        infoList.append((fstLevelKey, val))
                df = pd.DataFrame(infoList).rename(columns={0: 'Key', 1: 'Value'})
                style = df.style\
                    .set_table_styles([{'selector': 'th', 'props': [('text-align', 'left')]}])\
                    .set_properties(**{'text-align': 'left'})
                return style
            except:
                print("Found no metadata file at {0}.".format(self.metadataPath))
                return

        doiPart = self.doi.split("-")
        try:
            collectiondoi = doiPart[0] + "-" + doiPart[1]
        except:
            pass
        if len(doiPart) == 2:
            print('Collection')
            resDict = requests.get(self.response0.url, verify=self.doVerify).json()
        else:
            resDict = requests.get(self.response0.url + '?getDigitalFormats', verify=self.doVerify).json()
        infoList = []
        for fstLevelKey in resDict.keys():
            try:
                for scndLevelKey in resDict[fstLevelKey].keys():
                    val = resDict[fstLevelKey][scndLevelKey]
                    if val != '':
                        infoList.append((fstLevelKey, scndLevelKey, val))
            except:
                val = resDict[fstLevelKey]
                if val != '':
                    infoList.append((fstLevelKey, ' ', val))
        df = pd.DataFrame(infoList)\
            .rename(columns={0: 'Metadata', 1: 'Key', 2: 'Value'})\
            .set_index(['Metadata', 'Key'])
        style = df.style\
            .set_table_styles([{'selector': 'th', 'props': [('text-align', 'left')]}])\
            .set_properties(**{'text-align': 'left'})
        return style

    def datatype(self):
        if self.local:
            fileList = self.path.split(os.sep)[-1].split('.')
            if len(fileList) > 1:
                res = fileList[-1]
            else:
                res = fileList[0]
            return res
        try:
            f = requests.get(self.response0.url + '?getDigitalFormats', verify=self.doVerify).json()
            if 'Format' in f['Technical characteristics']:
                ret = f['Technical characteristics']['Format']
            elif 'Resource Type' in f['Technical characteristics']:
                ret = f['Technical characteristics']['Resource Type']
        except:
            raise ValueError("Can not determine regular format!")
        return ret

    def getdoi(self):
        return self.doi

    def response(self):
        return self.response0.url + '?getDigitalFormat'

    ######
    ##
    # File specific functions
    ##
    #####

    def json(self):
        return self.data.json()

    def jsonOriented(self):
        strData = json.dumps(self.json())
        return strData

    def df(self, dtype=False):
        return pd.DataFrame(self.json())

    def alternativefiles(self):
        return pd.DataFrame(self.alternatives.json())

    def collection(self):
        return requests.get(self.response0.url + '?getOverallJSON', verify=self.doVerify).json()

    def filename(self):
        return self.d

    def pdf(self):
        return HTML('<iframe src='+self.link+' width=900 height=550></iframe>')

    def debook(self):
        return HTML('<iframe src=''https://edition-topoi.org/dEbook/?pdf='+self.link+' + width=100% height=650></iframe>')

    def imageshow(self, w=500, h=500):
        data = requests.get(self.response0.url + '?getDigitalFormat', verify=self.doVerify)
        return Image(url=data.url, width=w, height=h)

    def imagesave(self, name="temp.jpg"):
        data = requests.get(self.response0.url + '?getDigitalFormat', verify=self.doVerify)
        with open(name, 'wb') as file:
            file.write(data.content)
        return name

    def digilib(self, w=1500, h=1950):
        path = self.response0.url+'#tabMode'
        path = path.replace('CitableHandler', 'collection')
        return HTML('<iframe src='+path+' + width=100% height=650></iframe>')

    def csv(self):
        text = self.data.iter_lines()
        ret = csv.reader(codecs.iterdecode(text, 'utf8'), delimiter=',')
        return ret

    def excel(self, name='./temp.xlsx'):
        data = self.data.content
        with open(name, 'wb') as file:
            file.write(data)
        return name

    def pickle(self, name='./temp.pickle'):
        data = self.data.content
        with open(name, 'wb') as file:
            file.write(data)
        return name

    def threedget(self, buttonInstance=False, filePath=False, dataTyp=False):
        files = self.alternatives.json()
        try:
            self.threedFormat
        except:
            self.threedFormat = 'ply'
        if dataTyp:
            self.threedFormat = dataTyp
        self.threedFilenames = []
        for file in files:
            ext = file['filename'].split('.')[-1]
            if ext.lower() == self.threedFormat:
                self.threedFilenames.append(file['filename'])
        if self.threedFilenames:
            for filename in self.threedFilenames:
                url = self.response0.url + '?getAlternativeFile=' + filename
                r = requests.get(url, verify=self.doVerify)
                if not filePath:
                    filePath = filename
                else:
                    filePath = os.path.join(filePath, filename)
                with open(filePath, 'wb') as w:
                    w.write(r.content)
                if buttonInstance:
                    with self.out:
                        print('Downloaded {0}'.format(filePath))
                return filePath
        else:
            print('No {0} file found.'.format(self.threedFormat))
            return None

    def threedview(self):
        path = self.response0.url+'#tabMode'
        path = path.replace('CitableHandler', 'collection')
        download = widgets.Button(
            description='Download 3D data',
            )
        self.out = widgets.Output()
        download.on_click(
            self.threedget
        )
        display(download, self.out)
        return HTML('<iframe src='+path+' + width=100% height=650></iframe>')

    def landingpage(self):
        return HTML('<iframe src='+self.landingpage_url+' + width=120% height=650></iframe>')

    ######
    ##
    # Resource specific functions
    ##
    #####

    def resources(self):
        """Returns all resources of a collection"""
        resources = []
        doiPart = self.doi.split("-")
        collectiondoi = doiPart[0] + "-" + doiPart[1]
        self.response0 = requests.get('https://dx.doi.org/{0}'.format(collectiondoi), verify=self.doVerify)
        objectdata = requests.get(self.response0.url + '?getOverallJSON', verify=self.doVerify).json()
        objectdatakeys = list(objectdata.keys())

        def check(doi):
            val = -1
            for k in objectdatakeys:
                try:
                    if objectdata[k]['doi'] == doi:
                        val = k
                except:
                    pass
            return val

        val = check(self.doi)
        if len(doiPart) > 2 and val == -1:
            print("The current DOI {0} corresponds to a digital resource, it is not a research object!".format(self.doi))
            return
        elif (len(doiPart) > 2 and val != -1):
            resources = self._getResource(val)
        elif (len(doiPart) == 2 and val == -1):
            resources = self._getResource()

        df = pd.DataFrame(resources)
        df.rename(columns={0: 'DOI', 1: 'Type', 2: 'Format'}, inplace=True)
        return df

    def _getResource(self, val=False):
        resources = []

        doiPart = self.doi.split("-")
        collectiondoi = doiPart[0] + "-" + doiPart[1]
        self.response0 = requests.get('https://dx.doi.org/{0}'.format(collectiondoi), verify=self.doVerify)
        objectdata = requests.get(self.response0.url + '?getOverallJSON', verify=self.doVerify).json()
        objectdatakeys = list(objectdata.keys())

        def getObjRes(objKey):
            curObj = objectdata[objKey]
            curObjRes = curObj["resources"]
            try:
                for resKey in curObjRes.keys():
                    try:
                        curRes = curObjRes[resKey]
                        for key in curRes.keys():
                            try:
                                techChar = curRes[key]['metadata']['Technical characteristics']
                                resType = techChar['Resource Type']
                                resFormat = techChar['Format']
                            except:
                                pass
                            for elem in curRes[key]["resources"]:
                                try:
                                    doi = elem["metadata"]["General Information"]["DOI"]
                                except:
                                    doi = 'None'
                                try:
                                    resType = elem["metadata"]["Technical characteristics"]["Resource Type"]
                                except:
                                    resType = 'None'
                                try:
                                    resFormat = elem["metadata"]["Technical characteristics"]["Format"]
                                except:
                                    resFormat = 'None'
                                resources.append((doi, resType, resFormat))
                    except:
                        pass
            except AttributeError:
                pass

        if not val:
            for objKey in objectdata.keys():
                getObjRes(objKey)
        elif val:
            getObjRes(val)

        return resources

    def digitalresource(self, asDataframe=True):
        """
        Returns the digital resource by comparing the format (=type) of
        resource and using the appropriate function.
        If applicable the standard return type is a dataframe,
        can be changed by choosing asDataframe=False.

        Loading from local files is partialy supported for text-like files.
        """

        format = self.datatype().lower()

        if self.local:
            def localJSON():
                try:
                    return pd.read_json(self.path, orient='table')
                except:
                    return pd.read_json(self.path)

            def localExcel():
                return pd.read_excel(self.path)

            def localCSV():
                return pd.read_csv(self.path)

            def localPickle():
                return pd.read_pickle(self.path)

            localFunctionMap = {
                'xls': localExcel,
                'xlsx': localExcel,
                'json': localJSON,
                'csv': localCSV,
                'pickle': localPickle,
            }

            return localFunctionMap[format]()

        if format in ['', 'json', 'jsonOriented', 'xls', 'csv', 'xlsx'] and asDataframe:
            try:
                df = pd.read_json(self.jsonOriented(), orient='table')
                return df
            except:
                pass
            try:
                df = pd.read_json(json.dumps(self.json()))
                return df
            except:
                pass
            try:
                df = pd.read_excel(self.excel())
                return df
            except:
                pass
            try:
                df = pd.DataFrame(list(self.csv()))
                return df
            except:
                pass

        if format == '' and asDataframe:
            raise ValueError('Could not convert {0} format to dataframe.'.format(format))

        if format in ['ply', 'nxs', 'xyz']:
            self.threedFormat = format

        functionMap = {
            'xls': self.excel,
            'xlsx': self.excel,
            'pdf': self.pdf,
            'json': self.json,
            'jsonOriented': self.jsonOriented,
            'csv': self.csv,
            'image': self.imageshow,
            'images': self.imageshow,
            'jpg': self.imageshow,
            'ply': self.threedview,
            'xyz': self.threedview,
            'nxs': self.threedview,
            'dataset': self.resource,
            'pickle': self.pickle,
        }

        return functionMap[format]()


# Final Function
def Citable(f_arg, *argv, formats="doi", project=False):
    """
    Load resource via a DOI which points to a Citable:
      call the function:

        - resource = Citable(DOI)  #for a single DOI
        - resource = Citable(DOI_1, DOI_2,....,DOI_n) # for more DOIs

      apply different methods on the resource (resource.func()):
        - note:
          one DOI -> resource.method()
          more DOI -> resource[i].method() with i=[0,1,...,n]

        - resource.metadata()  #the corresponding metadata
        - resource.json() #load json file
        - resource.df() #load json file as pandas dataframe
        - resource.debook() # load pdf with interactive tool 'dEbook-Viewer'
        - resource.pdf() # load PDF with standard viewer
        - resource.imageshow() # load image and show
        - resource.imagesave() # save image in local folder
        - resource.csv() # load csv file
        - resource.collection() # load overview json (each collections has its own overview json)
        - resource.docu() # a short introduction of collection & citable
        - resource.landingpage() # shows to the landing page of DOI
        - resource.filename() # returns file name
        - resource.datatype() # returns type of data (e.g. jpg or pdf)
        - resource.resource() # returns all digital resources including DOI
        - resource.getdoi() # returns DOI

      example:
        - single DOI:
          r=Citable('10.17171/1-3-388-1')
          r.filename()

        - two or more DOIs
          g=Citable('10.17171/1-1-3', '10.17171/1-1-4')
          g[1].metadata()

    """
    if type(f_arg) is pd.core.series.Series:
        lis = list(f_arg)
        liste = []
        for arg in lis:
            liste.append(Citableloader(arg, types=formats, project=project))
    if len(argv) == 0 and type(f_arg) is str:
        liste = Citableloader(f_arg, types=formats, project=project)
    if len(argv) == 0 and type(f_arg) is not str:
        liste = []
        for arg in f_arg:
            liste.append(Citableloader(arg, types=formats, project=project))
    if len(argv) != 0:
        liste = [Citableloader(f_arg, types=formats, project=project)]
        for arg in argv:
            liste.append(Citableloader(arg, types=formats, project=project))
    return liste
