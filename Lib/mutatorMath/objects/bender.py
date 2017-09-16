
import sys
from mutatorMath.objects.error import MutatorError
from mutatorMath.objects.location import Location, biasFromLocations
import mutatorMath.objects.mutator
from mutatorMath.objects.error import MutatorError


def noBend(loc, space=None): return loc

def validateMap(m):
    # validate the progress of the map
    # only increasing sections allowed
    # no horizontals or decreasing.
    m = m[:]
    m.sort()
    lx = None
    ly = None
    if len(m)<2:
        return False
    for x, y in m:
        if lx is None:
            lx = x
            ly = y
            continue
        dx = x-lx
        dy = y-ly
        if dy == 0:
            return False
        if dy < 0:
            return False
        lx = x
        ly = y
    return True

class WarpMutator(mutatorMath.objects.mutator.Mutator):
    def __call__(self, value):
        if isinstance(value, tuple):
            # handle split location
            return self.makeInstance(Location(w=value[0])), self.makeInstance(Location(w=value[1]))
        return self.makeInstance(Location(w=value))

"""

    A warpmap is a list of tuples that describe non-linear behaviour
    for a single dimension in a designspace.

    Bender is an object that accepts warpmaps and transforms
    locations accordingly.

    For instance:
        w = {'a': [(0, 0), (500, 200), (1000, 1000)]}
        b = Bender(w)
        assert b(Location(a=0)) == Location(a=0)
        assert b(Location(a=250)) == Location(a=100)
        assert b(Location(a=500)) == Location(a=200)
        assert b(Location(a=750)) == Location(a=600)
        assert b(Location(a=1000)) == Location(a=1000)

    A Mutator can use a Bender to transform the locations
    for its masters as well as its instances.
    Great care has to be taken not to mix up transformed / untransformed.
    So the changes in Mutator are small.
   
"""
class Bender(object):
    # object with a dictionary of warpmaps
    # call instance with a location to bend it
    def __init__(self, axes):
        # axes dict:
        #   { <axisname>: {'map':[], 'minimum':0, 'maximum':1000, 'default':0, 'tag':'aaaa', 'name':"longname"}}
        warpDict = {}
        self.warps = {}
        self.reversedWarps = {}
        for axisName, axisAttributes in axes.items():
            mapData = axisAttributes.get('map', [])
            if type(mapData)==list:
                if mapData==0:
                    # this axis has no bender
                    self.warps[axisName] = None
                    self.reversedWarps[axisName] = None
                else:
                    self.warps[axisName] = self._makeWarpFromList(axisName, mapData, axisAttributes['minimum'], axisAttributes['maximum'])
                    self.reversedWarps[axisName] = self._makeWarpFromList(axisName, mapData, axisAttributes['minimum'], axisAttributes['maximum'], reverse=True)

    def __repr__(self):
        return "<Bender warps:%s rev.warps:%s>"%(str(self.warps.items()), str(self.reversedWarps.items()))

    # def getMap(self, axisName):
    #     return self.maps.get(axisName, [])
            
    def _makeWarpFromList(self, axisName, warpMap, minimum, maximum, reverse=False):
        if not warpMap:
            warpMap = [(minimum,minimum), (maximum,maximum)]
        # check for the extremes, add if necessary
        # validate the graph only goes up
        if not sum([a==minimum for a, b in warpMap]):
            warpMap = [(minimum,minimum)] + warpMap
        if not sum([a==maximum for a, b in warpMap]):
            warpMap.append((maximum,maximum))
        if not validateMap(warpMap):
            raise MutatorError("invalid warp map:", mapData)
        items = []
        last = None
        for x, y in warpMap:
            if reverse:
                x, y = y, x
            items.append((Location(w=x), y))
        m = WarpMutator()
        items.sort()
        bias = biasFromLocations([loc for loc, obj in items], True)
        m.setBias(bias)
        n = None
        ofx = []
        onx = []
        for loc, obj in items:
            if (loc-bias).isOrigin():
                m.setNeutral(obj)
                break
        if m.getNeutral() is None:
            raise MutatorError("Did not find a neutral for this warp system", m)
        for loc, obj in items:
            lb = loc-bias
            if lb.isOrigin(): continue
            if lb.isOnAxis():
                onx.append((lb, obj-m.getNeutral()))
            else:
                ofx.append((lb, obj-m.getNeutral()))
        for loc, obj in onx:
            m.addDelta(loc, obj, punch=False,  axisOnly=True)
        for loc, obj in ofx:
            m.addDelta(loc, obj, punch=True,  axisOnly=True)
        return m

    def __call__(self, loc, space="design"):
        # bend a location according to the defined warps
        if space == "design":
            warpSource = self.warps
        elif space == "user":
            warpSource = self.reversedWarps
        new = loc.copy()
        for dim, warp in warpSource.items():
            if warp is None:
                new[dim] = loc[dim]
                continue
            if not dim in loc: continue
            try:
                new[dim] = warp(loc.get(dim))
            except:
                ex_type, ex, tb = sys.exc_info()
                raise MutatorError("A warpfunction \"%s\" (for axis \"%s\") raised \"%s\" at location %s"%(str(warp), dim, ex, loc.asString()), loc)
        return new

if __name__ == "__main__":
    # no bender
    assert noBend(Location(a=1234)) == Location(a=1234)
    assert noBend(Location(a=1234),space="user") == Location(a=1234)
    assert noBend(Location(a=(12,34))) == Location(a=(12,34))

    # linear map, single axis
    w = {'aaaa':{'map': [(0, 0), (1000, 1000)], 'name':'aaaaAxis', 'tag':'aaaa', 'minimum':0, 'maximum':1000, 'default':0}}
    b = Bender(w)
    assert b(Location(aaaa=0)) == Location(aaaa=0)
    assert b(Location(aaaa=500)) == Location(aaaa=500)
    assert b(Location(aaaa=(100,200))) == Location(aaaa=(100,200))
    assert b(Location(aaaa=1000)) == Location(aaaa=1000)
    # with reversed warp
    assert b(Location(aaaa=0),space="user") == Location(aaaa=0)
    assert b(Location(aaaa=500),space="user") == Location(aaaa=500)
    assert b(Location(aaaa=(100,200)),space="user") == Location(aaaa=(100,200))
    assert b(Location(aaaa=1000),space="user") == Location(aaaa=1000)

    # linear map, single axis
    w = {'aaaa':{'map': [(0, 100), (1000, 900)], 'name':'aaaaAxis', 'tag':'aaaa', 'minimum':0, 'maximum':1000, 'default':0}}
    b = Bender(w)
    assert b(Location(aaaa=0)) == Location(aaaa=100)
    assert b(Location(aaaa=500)) == Location(aaaa=500)
    assert b(Location(aaaa=1000)) == Location(aaaa=900)
    # with reversed warp
    assert b(Location(aaaa=100),space="user") == Location(aaaa=0)
    assert b(Location(aaaa=500),space="user") == Location(aaaa=500)
    assert b(Location(aaaa=900),space="user") == Location(aaaa=1000)

    # linear map, single axis, not mapped to 1000
    w = {'aaaa':{'map': [(-1, -2), (0,0), (1, 2)], 'name':'aaaaAxis', 'tag':'aaaa', 'minimum':-1, 'maximum':1, 'default':0}}
    b = Bender(w)
    assert b(Location(aaaa=(-1, 1))) == Location(aaaa=(-2,2))
    assert b(Location(aaaa=-1)) == Location(aaaa=-2)
    assert b(Location(aaaa=-0.5)) == Location(aaaa=-1)
    assert b(Location(aaaa=0)) == Location(aaaa=0)
    assert b(Location(aaaa=0.5)) == Location(aaaa=1)
    assert b(Location(aaaa=1)) == Location(aaaa=2)
    # with reversed warp
    a = b(Location(aaaa=(2,2)),space="user")
    assert b(Location(aaaa=(2,2)),space="user") == Location(aaaa=(1, 1))
    assert b(Location(aaaa=(-2,2)),space="user") == Location(aaaa=(-1, 1))
    assert b(Location(aaaa=-1),space="user") == Location(aaaa=-0.5)

    # one split map, single axis
    #w = {'a': [(0, 0), (500, 200), (600, 600)]}
    w = {'aaaa':{'map': [(0, 100), (500, 200), (600, 600)], 'name':'aaaaAxis', 'tag':'aaaa', 'minimum':0, 'maximum':600, 'default':0}}
    b = Bender(w)
    assert b(Location(aaaa=(100, 200))) == Location(aaaa=(120,140))
    assert b(Location(aaaa=0)) == Location(aaaa=100)
    assert b(Location(aaaa=250)) == Location(aaaa=150)
    assert b(Location(aaaa=500)) == Location(aaaa=200)
    assert b(Location(aaaa=600)) == Location(aaaa=600)
    assert b(Location(aaaa=750)) == Location(aaaa=1200)
    assert b(Location(aaaa=1000)) == Location(aaaa=2200)

    # implicit extremes
    w = {'aaaa':{'map': [(500, 200)], 'name':'aaaaAxis', 'tag':'aaaa', 'minimum':0, 'maximum':600, 'default':0}}
    b = Bender(w)
    assert b(Location(aaaa=(250, 100))) == Location(aaaa=(100, 40))
    assert b(Location(aaaa=0)) == Location(aaaa=0)
    assert b(Location(aaaa=250)) == Location(aaaa=100)
    assert b(Location(aaaa=500)) == Location(aaaa=200)
    assert b(Location(aaaa=600)) == Location(aaaa=600)
    assert b(Location(aaaa=750)) == Location(aaaa=1200)
    assert b(Location(aaaa=1000)) == Location(aaaa=2200)

    # check the reverse warps
    assert b(Location(aaaa=(100, 40)), space="user") == Location(aaaa=(250, 100))
    assert b(Location(aaaa=0), space="user") == Location(aaaa=0)
    assert b(Location(aaaa=100), space="user") == Location(aaaa=250)
    assert b(Location(aaaa=200), space="user") == Location(aaaa=500)
    assert b(Location(aaaa=600), space="user") == Location(aaaa=600)
    assert b(Location(aaaa=1200), space="user") == Location(aaaa=750)
    assert b(Location(aaaa=2200), space="user") == Location(aaaa=1000)

    #
    maps = [
            [(0,0), (100, 100), (200, 200)],                # wel
            [(200,0), (100, 100), (0, 200)],                # niet
            [(0,100), (100, 100), (100,100), (200, 200)],   # niet
            [(100, 100), (0,100), (100,100), (200, 200)],   # niet
            [(0,0), (1, 0.00001), (99, 100)]
        ]

    assert validateMap([(0,0), (100, 100), (200, 200)]) == True # regular increase
    assert validateMap([(200,0), (100, 100), (0, 200)]) == False # hidden decrease, mixed up
    assert validateMap([(0,100), (100, 100), (100,100), (200, 200)]) == False # Flat section between increases
    assert validateMap([(0,100), (100, 0), (200, 200)]) == False # Flat section between increases
    assert validateMap([(0,100)]) == False  # not a valid map
    assert validateMap([(0,100), (200,200)]) == True  # Smallest valid amap
    assert validateMap([(200,100), (0,200)]) == False  # Smallest invalid amap


