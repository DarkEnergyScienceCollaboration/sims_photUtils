import pyfits
import math
import numpy
import os

from lsst.sims.coordUtils import AstrometryBase

#scott's notes to self
#mixin could have a method by which user sets data dir and dust map file 
#(see main() below)
#otherwise, it defaults to values below
#only instantiate the map when you call for the ebv values

#however: that might get called before the user has a chance to intervene

#I guess if the user just set it in the base class as an attribute of the base
#class, the user would be able to intervene before the getter infrastructure 
#kicked in...

def interp1D(z1 , z2, offset):
    """ 1D interpolation on a grid"""

    zPrime = (z2-z1)*offset + z1

    return zPrime


            
class EbvMap(object):
    '''Class  for describing a map of EBV

    Images are read in from a fits file and assume a ZEA projection
    '''
        
    def readMapFits(self, fileName):
        """ read a fits file containing the ebv data"""
        hdulist = pyfits.open(fileName)
        self.header = hdulist[0].header
        self.data = hdulist[0].data
        self.nr = self.data.shape[0]
        self.nc = self.data.shape[1]

        #read WCS information
        self.cd11 = self.header['CD1_1']
        self.cd22 = self.header['CD2_2']
        self.cd12 = 0.
        self.cd21 = 0.

        self.crpix1 = self.header['CRPIX1']
        self.crval1 = self.header['CRVAL1']

        self.crpix2 = self.header['CRPIX2']
        self.crval2 = self.header['CRVAL2']

        # read projection information
        self.nsgp = self.header['LAM_NSGP']
        self.scale = self.header['LAM_SCAL']
        self.lonpole = self.header['LONPOLE']

    def skyToXY(self, gLon, gLat):
        """ convert long, lat angles to pixel x y

        input angles are in radians but the conversion assumes radians
        
        @param [in] gLon galactic longitude in radians
        
        @param [in] gLat galactic latitude in radians
        
        @param [out] x is the x pixel coordinate
        
        @param [out] y is the y pixel coordinate
        
        """

        rad2deg= 180./numpy.pi
        
        # use the SFD approach to define xy pixel positions
        # ROTATION - Equn (4) - degenerate case 
        if (self.crval2 > 89.9999):
            theta = gLat*rad2deg
            phi = gLon*rad2deg + 180.0 + self.lonpole - self.crval1
        elif (self.crval2 < -89.9999):
            theta = -gLat*rad2deg
            phi = self.lonpole + self.crval1 - gLon*rad2deg
        else:    
            # Assume it's an NGP projection ... 
            theta = gLat*rad2deg
            phi = gLon*rad2deg + 180.0 + self.lonpole - self.crval1

        # Put phi in the range [0,360) degrees 
        phi = phi - 360.0 * numpy.floor(phi/360.0);

        # FORWARD MAP PROJECTION - Equn (26) 
        Rtheta = 2.0 * rad2deg * numpy.sin((0.5 / rad2deg) * (90.0 - theta));

        # Equns (10), (11) 
        xr = Rtheta * numpy.sin(phi / rad2deg);
        yr = - Rtheta * numpy.cos(phi / rad2deg);
    
        # SCALE FROM PHYSICAL UNITS - Equn (3) after inverting the matrix 
        denom = self.cd11 * self.cd22 - self.cd12 * self.cd21;
        x = (self.cd22 * xr - self.cd12 * yr) / denom + (self.crpix1 - 1.0);
        y = (self.cd11 * yr - self.cd21 * xr) / denom + (self.crpix2 - 1.0);

        return x,y

    def generateEbv(self, glon, glat, interpolate = False):
        """ 
        Calculate EBV with option for interpolation
        
        @param [in] glon galactic longitude in radians
        
        @param [in] galactic latitude in radians
        
        @param [out] ebvVal the scalar value of EBV extinction
        
        """

        # calculate pixel values
        x,y = self.skyToXY(glon, glat)
        
        ix=numpy.array([int(xx+0.5) for xx in x])
        iy=numpy.array([int(yy+0.5) for yy in y])
        
      
        
        if (interpolate):
            ixLow=numpy.array([ii-1 if ii==self.nc-1 else ii for ii in ix])
            ixHigh=numpy.array([ii if ii==self.nc-1 else ii+1 for ii in ix])
            dx=numpy.array([ii-xx if ii==self.nc-1 else xx-ii for (ii,xx) in zip (ix,x)])
            
            """
            if (ix == self.nc-1):
                ixLow = ix-1
                ixHigh = ix
                dx = ix -x
            else:
                ixLow = ix
                ixHigh = ix+1                   
                dx = x - ix
            """
            
            iyLow=numpy.array([ii-1 if ii==self.nr-1 else ii for ii in iy])
            iyHigh=numpy.array([ii if ii==self.nr-1 else ii+1 for ii in iy])
            dy=numpy.array([ii-yy if ii==self.nr-1 else yy-ii for (ii,yy) in zip (iy,y)])
      
            """    
            if (iy == self.nr-1):
                iyLow = iy-1
                iyHigh = iy
                dy = iy - y
            else:
                iyLow = iy
                iyHigh = iy+1
                dy = y - iy
            """
         
            x1 = numpy.array([self.data[ii][jj] for (ii,jj) in zip(iyLow,ixLow)])
            x2 = numpy.array([self.data[ii][jj] for (ii,jj) in zip(iyLow,ixHigh)])
            xLow = interp1D(x1,x2,dx)
            
            x1 = numpy.array([self.data[ii][jj] for (ii,jj) in zip(iyHigh,ixLow)])
            x2 = numpy.array([self.data[ii][jj] for (ii,jj) in zip(iyHigh,ixHigh)])
            xHigh = interp1D(x1,x2,dx)
            
            #xLow = interp1D(self.data[iyLow][ixLow], self.data[iyLow][ixHigh], dx)
            #xHigh = interp1D(self.data[iyHigh][ixLow], self.data[iyHigh][ixHigh], dx)
            
            ebvVal = interp1D(xLow, xHigh, dy)                
         
        else:
            ebvVal = numpy.array([self.data[ii][jj] for (ii,jj) in zip(iy,ix)])
        
            #ebvVal = self.data[iy][ix]

        return ebvVal    
                        
    def skyToXYInt(self, gLong, gLat):
        x,y = self.skyToXY(gLong, gLat)
        ix = int(x+0.5)
        iy = int(y+0.5)

        return ix,iy



class EBVbase(object):
    """
    This class will give users access to calculateEbv oustide of the framework of a catalog.
    
    To find the value of EBV at a point on the sky, create an instance of this object, and
    then call calculateEbv passing the coordinates of interest as kwargs
    
    e.g.
    
    ebvObject = EBVbase()
    ebvValue = ebvObject(gLon = myLonValue, gLat = myLatValue)
    
    or 
    
    ebvValue = ebvObject(ra = myRA, dec = myDec)
    
    You can also specify dust maps in the northern and southern galactic hemispheres, but
    there are default values that the code will automatically load (see the class variables
    below).
    
    The information regarding where the dust maps are located is stored in
    member variables ebvDataDir, ebvMapNorthName, ebvMapSouthName
    
    The actual dust maps (when loaded) are stored in ebvMapNorth and ebvMapSouth
    """

    #these variables will tell the mixin where to get the dust maps
    ebvDataDir=os.environ.get("SIMS_DUSTMAPS_DIR")
    ebvMapNorthName="DustMaps/SFD_dust_4096_ngp.fits"
    ebvMapSouthName="DustMaps/SFD_dust_4096_sgp.fits"
    ebvMapNorth=None
    ebvMapSouth=None
    
        #the set_xxxx routines below will allow the user to point elsewhere for the dust maps
    def set_ebvMapNorth(self,word):
        """
        This allows the user to pick a new northern SFD map file
        """
        self.ebvMapNorthName=word
    
    def set_ebvMapSouth(self,word):
        """
        This allows the user to pick a new southern SFD map file
        """
        self.ebvMapSouthName=word
    
    #these routines will load the dust maps for the galactic north and south hemispheres
    def load_ebvMapNorth(self):
        """
        This will load the northern SFD map
        """
        self.ebvMapNorth=EbvMap()
        self.ebvMapNorth.readMapFits(os.path.join(self.ebvDataDir,self.ebvMapNorthName))
    
    def load_ebvMapSouth(self):
        """
        This will load the southern SFD map
        """
        self.ebvMapSouth=EbvMap()
        self.ebvMapSouth.readMapFits(os.path.join(self.ebvDataDir,self.ebvMapSouthName))
    
    def calculateEbv(self, gLon=None, gLat=None, ra=None, dec=None, northMap=None, southMap=None, 
                     interp=False):
        """ 
        For an array of Gal long, lat calculate E(B-V)
        
        
        @param [in] gLon galactic longitude in radians
        
        @param [in] gLat galactic latitude in radians
        
        @param [in] ra right ascension in radians
        
        @param [in] dec declination in radians
        
        @param [in] northMap the northern dust map
        
        @param [in] southMap the southern dust map
        
        @param [in] whether or not to interpolate the EBV value
        
        @param [out] ebv is a list of EBV values for all of the gLon, gLat pairs
        
        """
        
        #raise an error if the coordinates are only partially specified
        if (gLon is None and gLat is not None) or \
           (gLat is None and gLon is not None) or \
           (ra is None and dec is not None) or \
           (dec is None and ra is not None):
           
           if gLon is None:
               print "gLon is None"
           else:
               print "gLon is not None"
           
           if gLat is None:
               print "gLat is None"
           else:
               print "gLat is not None"
           
           if ra is None:
               print "ra is None"
           else:
               print "ra is not None"
           
           if dec is None:
               print "dec is None"
           else:
               print "dec is not None"
           
           raise RuntimeError("Inconsistent coordinates given to calculateEbv")  
         
        
        #raise an error if the coordinates are specified in both systems 
        if gLon is not None and gLat is not None:
            if ra is not None or dec is not None:
                raise RuntimeError("Specified both (gLon, gLat) and (ra, dec) in calculateEbv")        
        
        #convert (ra,dec) into gLon, gLat
        if gLon is None and gLat is None:
        
            #raise an error if you already specified ra or dec
            if ra is None or dec is None:
               raise RuntimeError("Must specify coordinates in calculateEbv")

            gLon, gLat = AstrometryBase.equatorialToGalactic(ra,dec)
        
        if northMap is None:
            if self.ebvMapNorth is None:
                self.load_ebvMapNorth()
            
            northMap = self.ebvMapNorth
        
        if southMap is None:
            if self.ebvMapSouth is None:
                self.load_ebvMapSouth()
            
            southMap = self.ebvMapSouth
        
        #taken from
        #http://stackoverflow.com/questions/4578590/python-equivalent-of-filter-getting-two-output-lists-i-e-partition-of-a-list
        
        ebv = None
        """
        what if we change the api to pass 
        galacticCoords or
        equatorialCoords
        
        so that we could do a list comprehension holding them together...
        """
        
        if gLat != []:
           
           ebv=numpy.zeros(len(gLon))
            
           nSet=numpy.array([(lon,lat,i) \
                                   for (lon,lat,i) in zip(gLon,gLat,range(len(gLon))) \
                                   if lat>0.0], \
                                   dtype=[('lon',float),('lat',float),('dex',int)])
        
           sSet=numpy.array([(lon,lat,i) \
                                   for (lon,lat,i) in zip(gLon,gLat,range(len(gLon))) \
                                   if lat<=0.0], \
                                   dtype=[('lon',float),('lat',float),('dex',int)])
            
           ebvNorth=northMap.generateEbv(nSet['lon'],nSet['lat'],interpolate=interp)
           ebvSouth=southMap.generateEbv(sSet['lon'],sSet['lat'],interpolate=interp)
            
           for (i,ee) in zip(nSet['dex'],ebvNorth):
               ebv[i]=ee
            
           for (i,ee) in zip(sSet['dex'],ebvSouth):
               ebv[i]=ee
        
        """
        ebv=[]
        for lon,lat in zip(gLon,gLat):
            if (lat <= 0.):
                ebv.append(southMap.generateEbv(lon,lat,interpolate=interp))
            else:
                ebv.append(northMap.generateEbv(lon,lat, interpolate=interp))
        """
        
        
        return ebv


class EBVmixin(EBVbase):
    """
    This mixin class contains the getters which a catalog object will use to call
    calculateEbv in the EBVbase class
    """
    
    
    #and finally, here is the getter
    def get_EBV(self):
        """
        Getter for the InstanceCatalog framework
        """

        glon=self.column_by_name('glon')
        glat=self.column_by_name('glat')
        
        EBV_out=numpy.array(self.calculateEbv(gLon=glon,gLat=glat,interp=True))
        return EBV_out
        
    def get_galacticRv(self):
        """
        Returns galactic RV by getting galacticAv and EBV and assuming Rv = Av/EBV"
        """
        Av=self.column_by_name('galacticAv')
        EBV=self.column_by_name('EBV')
        return numpy.array(Av/EBV)
    

