"""
Structural analysis of a T-shaped beam

Reference solution: 
 https://web.me.iastate.edu/jmchsu/files/Herrema_et_al-2018-CMAME.pdf

"""
from dolfinx.io import XDMFFile
from dolfinx.fem.petsc import (assemble_vector, assemble_matrix, apply_lifting)
from dolfinx.fem import (locate_dofs_topological, locate_dofs_geometrical,
                        dirichletbc, form, Constant, VectorFunctionSpace)
from dolfinx.mesh import locate_entities
import numpy as np
from mpi4py import MPI
from shell_analysis_fenicsX import *

t_beam = [#### quad mesh ####
        "t_beam_quad_80.xdmf",
        "t_beam_quad_320.xdmf",
        "t_beam_quad_1280.xdmf",
        "t_beam_quad_5120.xdmf",]
        
filename = "../../mesh/mesh-examples/t-junction/"+t_beam[2]
with dolfinx.io.XDMFFile(MPI.COMM_WORLD, filename, "r") as xdmf:
        mesh = xdmf.read_mesh(name="Grid")
      

E_val = 1e7
nu_val = 0.0
h_val = 0.1
f_val = -10.

E = Constant(mesh,E_val) # Young's modulus
nu = Constant(mesh,nu_val) # Poisson ratio
h = Constant(mesh,h_val) # Shell thickness
f = ufl.as_vector([0.,0.,f_val]) # Point force

element_type = "CG2CG1"

element = ShellElement(
                mesh,
                element_type
                )
W = element.W
w = Function(W)
dx_inplane, dx_shear = element.dx_inplane, element.dx_shear


#### Compute the CLT model from the material properties (for single-layer material)
material_model = MaterialModel(E=E,nu=nu,h=h)
elastic_model = ElasticModel(mesh,w,material_model.CLT)
elastic_energy = elastic_model.elasticEnergy(E, h, dx_inplane,dx_shear)
F = elastic_model.weakFormResidual(elastic_energy, f)

############ Set the BCs for the t-beam: one end fixed at x=0 ################

def boundary(x):
    return np.isclose(x[0], 0., atol=1e-6)

u0 = Function(W)
u0.vector.set(0.0)

facets = locate_entities(mesh, 1, boundary)
locate_fixed_BC = [locate_dofs_topological(W, 1, facets),]
bcs = [dirichletbc(u0,locate_fixed_BC)]

########### Apply the point load #############################
delta = Delta(x0=np.array([20.0, 0.0, 0.0]), f_p=(0.,0.,f_val))
f1 = Function(W)
f1_0,_ = f1.split()
f1_0.interpolate(delta.eval)


# Assemble linear system
a = derivative(F,w)
L = -F
A = assemble_matrix(form(a), bcs)
A.assemble()
b = assemble_vector(form(L))
b.setArray(f1.vector.getArray())
b.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE)
dolfinx.fem.set_bc(b, bcs)



######### Solve the linear system with KSP solver ############
solveKSP(A, b, w.vector)


########## Output: ##########
magnitude = computeNodalDispMagnitude(w.sub(0))
    
print("Maximum deflection magnitude from Herrema:", 0.0589)
print("Maximum deflection magnitude from this test:", 
                                np.max(magnitude))
print("  Number of elements = "+str(mesh.topology.index_map(mesh.topology.dim).size_local))
print("  Number of vertices = "+str(mesh.topology.index_map(0).size_local))

########## Visualization: ##############

u_mid, _ = w.split()
with XDMFFile(MPI.COMM_WORLD, "solutions/u_mid.xdmf", "w") as xdmf:
    xdmf.write_mesh(mesh)
    xdmf.write_function(u_mid)
