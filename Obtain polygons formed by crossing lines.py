import sys
import clr
clr.AddReference('ProtoGeometry')
from Autodesk.DesignScript.Geometry import *
from itertools import chain
import copy
import math

# crossing lines and the number of verticies obtained by the crossing, the number should be as small as possible because of a recursive function
lines = IN[0]
MAX_vertices = IN[1]

# this class represents a line and points at which the line crosses others
class Intersection:
	
	def __init__(self, line):
		self.line = line
		self.int_points = []		
	
	# using a standrad function to find intersection points
	def find_intersection(self, intersecting_line):
		intersection_point = Geometry.Intersect(self.line, intersecting_line)
		if len(intersection_point) != 0: self.int_points.append(intersection_point[0])
	
	# sort all point from the start point of the line	
	def connect_points(self):
		points = self.int_points
		if len(points) > 1:
			points.sort(key = lambda x: Geometry.DistanceTo(self.line.StartPoint, x))
			return PolyCurve.ByPoints(points).Curves()
		return None

# create two lists to store intersection all points and curves
int_points = []
curves = []

# pass all point and curves to "curves"
for ln in lines:
	obj = Intersection(ln)
	for ln__ in lines:
		if ln != ln__:
			obj.find_intersection(ln__)
	for p1 in obj.int_points:
		if any([Geometry.IsAlmostEqualTo(p1, p2) for p2 in int_points]) == False:
			int_points.append(p1)
	curves.extend(obj.connect_points())	

# drop a line if it is identical with another
for i in range(len(curves)-1):
	for j in range(i+1,len(curves)):
		if Geometry.IsAlmostEqualTo(curves[i], curves[j]):
			curves.pop(j)
			break

# this function convex hull taken from Springs and slightly adjusted
# the point for using this is to sort neighbouring nodes clockwise
def points_convex_hull2d(points, p0):
	
	pts = sorted((p.X, p.Y) for p in points)
	
	def pCrs(o, a, b):
		return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
		
	pLen = len(pts)
	
	if pLen < 3:	
		return [Point.ByCoordinates(p[0], p[1], 0) for p in pts]
	else:
		lower, upper = [], []
		for i in xrange(pLen):
			j = pLen - 1 - i
			while len(lower) >= 2 and pCrs(lower[-2], lower[-1], pts[i]) <= 0.000001:
				lower.pop()
			lower.append(pts[i])
			while len(upper) >= 2 and pCrs(upper[-2], upper[-1], pts[j]) <= 0.000001:
				upper.pop()
			upper.append(pts[j])
		
		lower.pop()
		upper.pop()
		
		return [Point.ByCoordinates(p[0], p[1], 0) for p in chain(lower, upper)]
		

# it represents an intersection point
class Node:
	
	def __init__(self, point):
		self.point = point
		self.sides = []
		self.nodes = []
	
	# add a side if it's not been added yet
	def add_side(self, side):
		if any([Geometry.IsAlmostEqualTo(side, side_) for side_ in self.sides]) == False:
			self.sides.append(side)
			
	# add a neighbouring node
	def add_node(self, node):
		self.nodes.append(node)
	
	# find connection between two nodes 
	def find_connected_nodes(node1, node2):
		common_sides = set(node1.sides).intersection(set(node2.sides))
		if len(common_sides) != 0:
			node1.add_node(node2)
			node2.add_node(node1)
	
	# sort node clockwise 
	def sort_nodes_using_convex_hull(self):
		points = points_convex_hull2d([n.point for n in self.nodes], self.point)
		sorted_nodes = []
		for p in points:
			for n in self.nodes:
				if n not in sorted_nodes:
					if Geometry.IsAlmostEqualTo(p, n.point):
						sorted_nodes.append(n)
		self.nodes = sorted_nodes
		return None

# store all nodes in a list
nodes = []

# create nodes and pass them to "nodes"
for point in int_points:
	new_node = Node(point)
	for curv in curves:
		if Geometry.IsAlmostEqualTo(point, curv.StartPoint) or Geometry.IsAlmostEqualTo(point, curv.EndPoint):
		 	new_node.add_side(curv)
	nodes.append(new_node)
	
# make connections between nodes based on common lines
for i in range(len(nodes)-1):
	for j in range(i+1, len(nodes)):
		Node.find_connected_nodes(nodes[i], nodes[j])
		
# recursive function to create all possible paths from each node
def walk_through(node, paths, used_nodes = []):
	used_nodes.append(node)
	for node__ in node.nodes:
		# if at least after two steps the path leads to the initial node the fucntion terminates
		if len(used_nodes) > 2 and node__ == used_nodes[0]:
			paths.append(used_nodes)
			return None
		# to restrict the number of steps (nodes) MAX_vertices has been implemented
		if node__ not in used_nodes and len(used_nodes) < MAX_vertices:
			walk_through(node__, paths, copy.copy(used_nodes))

# get outline from nodes
def get_outline(nodes):

	# transform a point with respect to a new coordinate system
	def transform_point(point, origin_point, angle):
		x = point.X - origin_point.X
		y = point.Y - origin_point.Y
		x_transformed = x*math.cos(angle * math.pi/180) + y*math.sin(angle * math.pi/180)
		y_transformed = -x*math.sin(angle * math.pi/180) + y*math.cos(angle * math.pi/180)
		return x_transformed, y_transformed
	
	# get the index of the most right node
	def get_index_of_most_right_node(transf_points):
	
		def check_if_nodes_on_left(lst):
			for point in lst:
				if point[0] > 0.000001:
					return False
			return True
		for	i, lst in enumerate(transf_points):
			if check_if_nodes_on_left(lst):
				return i
		return None			
	
	# get the most left node
	node_ = sorted(nodes, key = lambda x : x.point.X)[0]
	outline = []
	outline.append(node_)
	
	for i in range(len(nodes)):
		transf_points = []
		neighbouring_nodes) = [n for n in node_.nodes if n not in outline]
		if len(neighbouring_nodes) > 0:
			for k, n_ in enumerate(neighbouring_nodes):
				v_ = Vector.ByTwoPoints(node_.point, n_.point)
				# rotation in reference to Y axis and therefore -360
				angle = -360 + Vector.AngleAboutAxis(Vector.YAxis(), v_, Vector.ZAxis())
				transf_points.append([transform_point(n_.point, node_.point, angle) for x, n_ in enumerate(neighbouring_nodes) if k != x])
			node_ = neighbouring_nodes[get_index_of_most_right_node(transf_points)]
			outline.append(node_)
		# it terminates when it meets the first node
		if len(outline) > 2 and outline[0] in node_.nodes:
			return outline
	return outline
	
outline = get_outline(nodes)

paths_filtered = []

# create all possible path from each node and filter them based on neighbouring nodes  
for node in nodes:
	paths = []
	walk_through(node, paths, [])
	node.sort_nodes_using_convex_hull()
	paths.sort(key=len)
	neighboring_nodes = copy.copy(node.nodes)
	if len(neighboring_nodes) > 2:
		neighboring_nodes.append(neighboring_nodes[0])
	for i in range(len(neighboring_nodes)-1):
		# omit paths which lead through two points laying on the outline except for triangles
		if neighboring_nodes[i] in outline and neighboring_nodes[i+1] in outline and len(neighboring_nodes) > 2:
			continue
		# otherwise if two nodes are included in one path that means it takes a path the most minimal number of nodes (steps)
		else:
			for path in paths:
				if neighboring_nodes[i] in path and neighboring_nodes[i+1] in path:
					paths_filtered.append(path)
					break

# compare two polygons to check if they are identical
def if_polygons_same_szie(polygon1, polygon2):
	if len(polygon1) == len(polygon2):
		count = 0
		for p1 in polygon1:
			for j, p2 in enumerate(polygon2):
				if Geometry.IsAlmostEqualTo(p1,p2):
					count += 1
					break
		if count == len(polygon1):
			return True
		else:
			return False
	else:
		return False

polygons = [[n_.point for n_ in path] for path in paths_filtered]

# drop dublicates from polygons
i = 0
while(i < len(polygons)-1):
	for j in range(i+1, len(polygons)):
		if if_polygons_same_szie(polygons[i], polygons[j]):
			polygons.pop(j)
			i -= 1
			break
	i += 1


OUT = polygons

