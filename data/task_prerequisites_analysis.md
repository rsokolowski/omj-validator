# OMJ Task Prerequisites Analysis

This file contains the comprehensive analysis of all 247 OMJ tasks, identifying skills, techniques, and suggested prerequisite relationships. This is a draft for manual review and cleanup before translating into the task JSON structure.

## Skill Taxonomy

Based on the analysis, the following recurring skill categories were identified:

### Number Theory
- **Modular arithmetic** - analyzing expressions mod n
- **Prime factorization** - using prime properties
- **Divisibility arguments** - proving divisibility conditions
- **Diophantine equations** - solving integer equations
- **Digit manipulation** - digit sums, place value

### Algebra
- **Symmetric systems** - solving cyclic/symmetric equations
- **Nested radicals** - denesting radical expressions
- **Algebraic identities** - factorization, completing the square
- **Inequality manipulation** - AM-GM, Cauchy-Schwarz
- **Polynomial analysis** - roots, factorization

### Geometry
- **Angle chasing** - using angle relationships
- **Circle theorems** - inscribed angles, tangent properties
- **Area methods** - decomposition, invariants
- **Coordinate geometry** - analytic approach
- **3D spatial reasoning** - volumes, cross-sections
- **Transformation techniques** - reflection, rotation

### Combinatorics
- **Pigeonhole principle** - existence arguments
- **Parity arguments** - odd/even analysis
- **Invariants/monovariants** - quantities that don't change
- **Graph theory** - degrees, colorings, matchings
- **Counting techniques** - systematic enumeration

### Logic
- **Case analysis** - exhaustive checking
- **Proof by contradiction** - impossibility arguments
- **Constructive proofs** - building examples

---

## Year 2005

### 2005_etap1_1 (Nested radicals)
- **Skills needed:** Nested radical simplification, algebraic manipulation, pattern recognition
- **Skills gained:** Denesting radicals using $\sqrt{a \pm \sqrt{b}} = \sqrt{x} \pm \sqrt{y}$ form
- **Prereqs:** none (foundational)

### 2005_etap1_2 (Inscribed circle + perpendicular diagonals)
- **Skills needed:** Tangential quadrilateral properties, perpendicular diagonals
- **Skills gained:** Relationship between inscribed circles and diagonal properties
- **Prereqs:** none

### 2005_etap1_3 (99 points in circle - pigeonhole)
- **Skills needed:** Pigeonhole principle, geometric covering arguments
- **Skills gained:** Pigeonhole in geometric configurations
- **Prereqs:** none (foundational for pigeonhole)

### 2005_etap1_4 (Symmetric system)
- **Skills needed:** Symmetric systems, algebraic manipulation
- **Skills gained:** Solving cyclic/symmetric systems
- **Prereqs:** none (foundational for symmetric systems)

### 2005_etap1_5 (121 apples in 15 buckets)
- **Skills needed:** Arithmetic series sum, basic combinatorics
- **Skills gained:** Minimum sum of distinct positive integers
- **Prereqs:** none

### 2005_etap1_6 (Coin weighing - 5 coins, 48g)
- **Skills needed:** Information theory, binary search, logical case analysis
- **Skills gained:** Coin weighing problem strategies
- **Prereqs:** none

### 2005_etap1_7 (Points with AB=BC=BD=17)
- **Skills needed:** Coordinate geometry, distance formula, Pythagorean theorem
- **Skills gained:** Using coordinates to solve geometric problems
- **Prereqs:** none

### 2005_etap2_1 (Prism vs pyramid faces)
- **Skills needed:** Euler's formula, polyhedra counting
- **Skills gained:** Polyhedron combinatorics
- **Prereqs:** none

### 2005_etap2_2 (111 numbers - sum divisible by 11)
- **Skills needed:** Pigeonhole principle, modular arithmetic
- **Skills gained:** Combining pigeonhole with residue classes
- **Prereqs:** 2005_etap1_3

### 2005_etap2_3 (Triangle with 45° angle and orthocenter)
- **Skills needed:** Orthocenter properties, angle chasing
- **Skills gained:** Orthocenter distance relationships
- **Prereqs:** none

### 2005_etap2_4 (14^n - 9 prime)
- **Skills needed:** Modular arithmetic, divisibility analysis, Fermat's Little Theorem
- **Skills gained:** Primality testing with algebraic constraints
- **Prereqs:** none (foundational for primality)

### 2005_etap2_5 (Hexagon area bound)
- **Skills needed:** Hexagon angle sums, area inequalities
- **Skills gained:** Bounding polygon areas
- **Prereqs:** none

---

## Year 2006

### 2006_etap1_1 (Digit sum of product = 2006²)
- **Skills needed:** Digit sum properties, modular arithmetic (mod 9)
- **Skills gained:** Digit sum behavior under multiplication
- **Prereqs:** none (foundational for digit sums)

### 2006_etap1_2 (Right triangle with square APBQ)
- **Skills needed:** Square properties, perpendicular lines
- **Skills gained:** Perpendicularity from square constructions
- **Prereqs:** none

### 2006_etap1_3 (Prime triples q=p²+6)
- **Skills needed:** Modular arithmetic with primes, testing small cases
- **Skills gained:** Systematic prime equation analysis
- **Prereqs:** 2005_etap2_4

### 2006_etap1_4 (Triangle with 120° angle, median bound)
- **Skills needed:** Median length formula, triangle inequalities
- **Skills gained:** Using median properties with special angles
- **Prereqs:** none

### 2006_etap1_5 (xy^n < x⁴+y⁴ inequality)
- **Skills needed:** AM-GM inequality, boundary analysis
- **Skills gained:** Finding boundary values in inequalities
- **Prereqs:** none

### 2006_etap1_6 (Tetrahedron with obtuse face)
- **Skills needed:** 3D geometry, circumsphere properties
- **Skills gained:** Circumcenter inside/outside tetrahedra
- **Prereqs:** none

### 2006_etap1_7 (17-gon, 10 vertices form trapezoid)
- **Skills needed:** Pigeonhole principle, combinatorial geometry
- **Skills gained:** Advanced pigeonhole in regular polygons
- **Prereqs:** 2005_etap2_2

### 2006_etap2_1 (System a²+b²+c²=23, a+2b+4c=22)
- **Skills needed:** Cauchy-Schwarz inequality, system solving
- **Skills gained:** Using Cauchy-Schwarz to solve constrained systems
- **Prereqs:** none

### 2006_etap2_2 (120° hexagon - perpendicular bisectors)
- **Skills needed:** 120° angles, perpendicular bisector concurrence
- **Skills gained:** Using angle constraints to prove concurrence
- **Prereqs:** none

### 2006_etap2_3 (6 points, 10 edges - triangle exists)
- **Skills needed:** Graph theory basics, extremal graph theory
- **Skills gained:** Triangle existence in dense graphs
- **Prereqs:** none (foundational for graph theory)

### 2006_etap2_4 (Product ends in "10")
- **Skills needed:** Modular arithmetic, last digit analysis
- **Skills gained:** Analyzing products modulo 100
- **Prereqs:** 2006_etap1_1

### 2006_etap2_5 (Pyramid with 20° apex angles)
- **Skills needed:** 3D geometry, triangle inequality
- **Skills gained:** Relating apex angles to base perimeter
- **Prereqs:** none

---

## Year 2007

### 2007_etap1_1 (Nested absolute values)
- **Skills needed:** Nested absolute value solving, case analysis
- **Skills gained:** Peeling nested absolute values
- **Prereqs:** none

### 2007_etap1_2 (Quadrilateral KLMN from reflections)
- **Skills needed:** Point reflection, area transformations
- **Skills gained:** Area computation via reflections
- **Prereqs:** none

### 2007_etap1_3 (Telescoping inequality with fractions)
- **Skills needed:** Telescoping series, algebraic manipulation
- **Skills gained:** Recognizing telescoping patterns
- **Prereqs:** none

### 2007_etap1_4 (8-digit number divisible by 101)
- **Skills needed:** Modular arithmetic, cyclic number properties
- **Skills gained:** Cyclic permutation divisibility invariance
- **Prereqs:** 2006_etap1_1

### 2007_etap1_5 (Inscribed circle with angle conditions)
- **Skills needed:** Tangential quadrilateral, angle-chord relationships
- **Skills gained:** Complex angle-chord relationships
- **Prereqs:** 2005_etap1_2

### 2007_etap1_6 (15-digit numbers with 0 in every triple)
- **Skills needed:** Combinatorial counting, digit constraints
- **Skills gained:** Counting sequences with local constraints
- **Prereqs:** none

### 2007_etap1_7 (Pyramid cross-section > base)
- **Skills needed:** 3D geometry, cross-section analysis
- **Skills gained:** Cross-section area optimization
- **Prereqs:** none

### 2007_etap2_1 (AM-GM implies irrational)
- **Skills needed:** AM-GM, irrationality proofs
- **Skills gained:** Proving existence of irrational numbers
- **Prereqs:** none (foundational for irrationality)

### 2007_etap2_2 (4×4 grid - three equal sums)
- **Skills needed:** Pigeonhole principle, bounded sums
- **Skills gained:** Pigeonhole with bounded values
- **Prereqs:** 2005_etap2_2

### 2007_etap2_3 (Regular hexagon area equality)
- **Skills needed:** Regular hexagon symmetry, area dissection
- **Skills gained:** Using symmetry for area proofs
- **Prereqs:** none

### 2007_etap2_4 (2^m not sum of consecutive)
- **Skills needed:** Odd/even analysis, consecutive sum formula
- **Skills gained:** When powers of 2 can't be consecutive sums
- **Prereqs:** none

### 2007_etap2_5 (Cube pentagon cross-section bisecting volume)
- **Skills needed:** 3D geometry, cube sections, volume computation
- **Skills gained:** Pentagon cross-sections of cubes
- **Prereqs:** none

---

## Year 2008

### 2008_etap1_1 (|x|+|y|=1 intersections with line)
- **Skills needed:** Absolute value equations, graphical interpretation
- **Skills gained:** Counting intersections with absolute value sets
- **Prereqs:** 2007_etap1_1

### 2008_etap1_2 (Box with given diagonal and surface area)
- **Skills needed:** 3D geometry, Pythagorean theorem, surface area
- **Skills gained:** Relating diagonal and surface to edge sum
- **Prereqs:** none

### 2008_etap1_3 (Sum of squared distances to line through square center)
- **Skills needed:** Coordinate geometry, distance formula
- **Skills gained:** Sum of squared distances invariant
- **Prereqs:** none

### 2008_etap1_4 (a+b prime, a³+b³ divisible by 3)
- **Skills needed:** Modular arithmetic, prime analysis
- **Skills gained:** Combining primality with divisibility
- **Prereqs:** 2006_etap1_3

### 2008_etap1_5 (Angle bisector length bound)
- **Skills needed:** Angle bisector theorem, triangle inequalities
- **Skills gained:** Bounding angle bisector length
- **Prereqs:** none

### 2008_etap1_6 (2-coloring of plane - isosceles right triangle)
- **Skills needed:** Ramsey theory, pigeonhole principle
- **Skills gained:** Ramsey-type results in geometry
- **Prereqs:** 2005_etap1_3

### 2008_etap1_7 (Polyhedron with 4,6,8-sided projections)
- **Skills needed:** 3D polyhedra, orthogonal projections
- **Skills gained:** Understanding projection shapes
- **Prereqs:** 2005_etap2_1

### 2008_etap2_1 (Ratio equations with odd numbers)
- **Skills needed:** Algebraic manipulation, ratio equations
- **Skills gained:** Solving symmetric ratio equations
- **Prereqs:** 2005_etap1_4

### 2008_etap2_2 (Minimize sum of ±1 products)
- **Skills needed:** Parity analysis, circular arrangements
- **Skills gained:** Minimizing cyclic products
- **Prereqs:** none

### 2008_etap2_3 (Parallelogram area with parallel line)
- **Skills needed:** Parallel lines, area transformations
- **Skills gained:** Area preservation under parallel transformations
- **Prereqs:** none

### 2008_etap2_4 (Tournament - everyone same wins)
- **Skills needed:** Graph theory, handshaking lemma
- **Skills gained:** Tournament degree sequence analysis
- **Prereqs:** none

### 2008_etap2_5 (Hexagonal pyramid - lines concurrent)
- **Skills needed:** 3D geometry, Brianchon's theorem
- **Skills gained:** Concurrence in pyramid cross-sections
- **Prereqs:** none

---

## Year 2009

### 2009_etap1_1 (a²=b²+c with all prime)
- **Skills needed:** Prime number properties, quadratic equations
- **Skills gained:** Testing small primes in quadratic relationships
- **Prereqs:** none

### 2009_etap1_2 (Trapezoid - sum of areas condition)
- **Skills needed:** Area relationships in trapezoids, locus problems
- **Skills gained:** Finding locus with area constraints
- **Prereqs:** none

### 2009_etap1_3 (a+b+c+d=101, ab+cd=200 parity)
- **Skills needed:** Parity analysis, algebraic manipulation
- **Skills gained:** Using parity for existence proofs
- **Prereqs:** 2005_etap1_5

### 2009_etap1_4 (18-gon rectangle)
- **Skills needed:** Regular polygon geometry, parallel lines
- **Skills gained:** Using symmetry in regular polygons
- **Prereqs:** none

### 2009_etap1_5 (55 numbers not divisible by 5 - quadratic residues)
- **Skills needed:** Modular arithmetic, quadratic residues, pigeonhole
- **Skills gained:** Pigeonhole with quadratic residues
- **Prereqs:** 2005_etap2_2, 2009_etap1_3

### 2009_etap1_6 (Regular tetrahedron cross-section perimeter)
- **Skills needed:** 3D geometry, optimization
- **Skills gained:** Minimizing cross-section perimeter
- **Prereqs:** none

### 2009_etap1_7 (a²+a and a³+a rational implies a rational)
- **Skills needed:** Algebraic manipulation, rationality proofs
- **Skills gained:** Proving rationality from polynomial constraints
- **Prereqs:** 2007_etap2_1

### 2009_etap2_1 (Sum of any 11 > remaining 10)
- **Skills needed:** Linear inequalities, sum analysis
- **Skills gained:** Using overlapping subset sums
- **Prereqs:** none

### 2009_etap2_2 (Trapezoid with 60° angles)
- **Skills needed:** Trapezoid geometry, angle chasing
- **Skills gained:** Using 60° angles to prove equality
- **Prereqs:** none

### 2009_etap2_3 (n²+n+1 and n²+n+3 both prime)
- **Skills needed:** Prime analysis, divisibility arguments
- **Skills gained:** When consecutive quadratics are both prime
- **Prereqs:** 2006_etap1_3

### 2009_etap2_4 (6 people, each knows 3 - 4-cycle of friends)
- **Skills needed:** Graph theory, friendship graphs
- **Skills gained:** Finding cycles in regular graphs
- **Prereqs:** 2006_etap2_3

### 2009_etap2_5 (Pyramid - each lateral edge perpendicular to base edge)
- **Skills needed:** 3D geometry, perpendicularity in space
- **Skills gained:** Skew perpendicular lines in pyramids
- **Prereqs:** 2006_etap1_6

---

## Year 2010

### 2010_etap1_1 (Symmetric system x+y=xy)
- **Skills needed:** Symmetric systems, factoring
- **Skills gained:** Recognizing symmetric structures
- **Prereqs:** none (foundational for 2010s symmetric problems)

### 2010_etap1_2 (Tetrahedron circumcenter and heights)
- **Skills needed:** 3D geometry, circumcenter properties
- **Skills gained:** Circumcenter-height relationships in 3D
- **Prereqs:** none

### 2010_etap1_3 (Square root inequality)
- **Skills needed:** Inequality manipulation, squaring
- **Skills gained:** Proving inequalities with square roots
- **Prereqs:** none

### 2010_etap1_4 (Midpoint area invariance)
- **Skills needed:** Vector geometry, area invariance
- **Skills gained:** Area calculations using vectors
- **Prereqs:** none (foundational for area methods)

### 2010_etap1_5 (L-shaped pieces - invariant)
- **Skills needed:** Invariants, pattern recognition
- **Skills gained:** Finding and using invariants
- **Prereqs:** none (foundational for invariants)

### 2010_etap1_6 (Cyclic quadrilateral with perpendiculars)
- **Skills needed:** Cyclic quadrilateral properties, circle theorems
- **Skills gained:** Working with perpendiculars and cyclic quadrilaterals
- **Prereqs:** none

### 2010_etap1_7 (No integer solutions mod 4)
- **Skills needed:** Modular arithmetic, Diophantine equations
- **Skills gained:** Using modular arithmetic for non-existence
- **Prereqs:** none

### 2010_etap2_1 (Pentagon area with parallelism)
- **Skills needed:** Area relationships, parallelism
- **Skills gained:** Complex area manipulation
- **Prereqs:** 2010_etap1_4

### 2010_etap2_2 (Divisibility with GCD)
- **Skills needed:** Divisibility, GCD properties
- **Skills gained:** Symmetric divisibility conditions
- **Prereqs:** none

### 2010_etap2_3 (Tournament cycles)
- **Skills needed:** Graph theory, tournament properties
- **Skills gained:** Finding cycles in tournaments
- **Prereqs:** none

### 2010_etap2_4 (Constrained inequality)
- **Skills needed:** AM-GM, algebraic manipulation
- **Skills gained:** Proving inequalities with constraints
- **Prereqs:** 2010_etap1_3

### 2010_etap2_5 (Sphere packing in tetrahedron)
- **Skills needed:** 3D packing, sphere geometry
- **Skills gained:** Sphere packing in polyhedra
- **Prereqs:** none

---

## Year 2011

### 2011_etap1_1 (No solution - square root constraint)
- **Skills needed:** Inequality analysis, non-negativity
- **Skills gained:** Using algebraic constraints for impossibility
- **Prereqs:** none

### 2011_etap1_2 (Isosceles triangle angles)
- **Skills needed:** Isosceles triangle properties, angle chasing
- **Skills gained:** Solving for angles with constraints
- **Prereqs:** none

### 2011_etap1_3 (Rectangle diagonal relationship)
- **Skills needed:** Rectangle properties, algebraic manipulation
- **Skills gained:** Deriving diagonal relationships
- **Prereqs:** none

### 2011_etap1_4 (Prime factorization with 5)
- **Skills needed:** Prime factorization, divisibility by 5
- **Skills gained:** Using prime factorization for constraints
- **Prereqs:** none

### 2011_etap1_5 (Triangle inequality with perpendiculars)
- **Skills needed:** Triangle inequality, perpendicular properties
- **Skills gained:** Distance bounds using perpendiculars
- **Prereqs:** none

### 2011_etap1_6 (Sum of square roots rational)
- **Skills needed:** Rationality conditions, algebraic field extensions
- **Skills gained:** When sums of square roots are rational
- **Prereqs:** none

### 2011_etap1_7 (3D distance minimization)
- **Skills needed:** 3D coordinate geometry, projection
- **Skills gained:** Minimum distances using projections
- **Prereqs:** none

### 2011_etap2_1 (Divisibility by 5,7,25)
- **Skills needed:** Divisibility case analysis, Diophantine equations
- **Skills gained:** Systematic case analysis
- **Prereqs:** 2011_etap1_4

### 2011_etap2_2 (Tournament parity)
- **Skills needed:** Pigeonhole principle, parity arguments
- **Skills gained:** Using parity in tournaments
- **Prereqs:** none

### 2011_etap2_3 (Triangle area formula achievability)
- **Skills needed:** Heron's formula, trigonometry
- **Skills gained:** Analyzing when area formulas are achievable
- **Prereqs:** none

### 2011_etap2_4 (Symmetric constrained equation)
- **Skills needed:** Symmetric equations, constraint analysis
- **Skills gained:** Finding all solutions to symmetric equations
- **Prereqs:** 2010_etap1_1

### 2011_etap2_5 (Circle with angle bisector)
- **Skills needed:** Circle geometry, angle bisector properties
- **Skills gained:** Using circumcenter and angle relationships
- **Prereqs:** 2010_etap1_6

---

## Year 2012

### 2012_etap1_1 (Powers mod 10)
- **Skills needed:** Modular arithmetic, Fermat's Little Theorem
- **Skills gained:** Periodicity of powers modulo 10
- **Prereqs:** none

### 2012_etap1_2 (Angle bisector isosceles)
- **Skills needed:** Angle bisectors, isosceles triangles
- **Skills gained:** Using bisectors to establish equal distances
- **Prereqs:** 2011_etap1_2

### 2012_etap1_3 (Digit manipulation equation)
- **Skills needed:** Digit manipulation, systematic enumeration
- **Skills gained:** Setting up digit-based equations
- **Prereqs:** none

### 2012_etap1_4 (Pigeonhole in graph-like structure)
- **Skills needed:** Pigeonhole principle, bipartite structure
- **Skills gained:** Pigeonhole in graph structures
- **Prereqs:** 2011_etap2_2

### 2012_etap1_5 (Area with heights)
- **Skills needed:** Area calculation, height relationships
- **Skills gained:** Complex area decomposition
- **Prereqs:** none

### 2012_etap1_6 (Inscribed sphere angle sums)
- **Skills needed:** Inscribed sphere properties, solid angles
- **Skills gained:** Angle sums in pyramids with inscribed spheres
- **Prereqs:** none

### 2012_etap1_7 (Perfect square factorization)
- **Skills needed:** Factorization, perfect square analysis
- **Skills gained:** When factored expressions are perfect squares
- **Prereqs:** 2010_etap1_7

### 2012_etap2_1 (Linear equation with inequalities)
- **Skills needed:** Linear equations, inequality constraints
- **Skills gained:** Finding integer solutions with constraints
- **Prereqs:** none

### 2012_etap2_2 (Integer-sided triangle area)
- **Skills needed:** Heron's formula, integer constraints
- **Skills gained:** Constraints on integer-sided triangles
- **Prereqs:** 2011_etap2_3

### 2012_etap2_3 (Constrained inequality - AM-GM)
- **Skills needed:** AM-GM, function analysis
- **Skills gained:** Proving inequalities with multiple methods
- **Prereqs:** 2010_etap2_4

### 2012_etap2_4 (Coloring arguments)
- **Skills needed:** Combinatorial reasoning, coloring
- **Skills gained:** Limitations in geometric colorings
- **Prereqs:** none

### 2012_etap2_5 (Prime quadratic forms)
- **Skills needed:** Prime properties, quadratic forms
- **Skills gained:** Analyzing quadratic expressions with primes
- **Prereqs:** 2011_etap1_4

---

## Year 2013

### 2013_etap1_1 (Percentage constraint - max attendance)
- **Skills needed:** Percentage calculations, divisibility
- **Skills gained:** Solving real-world percentage problems
- **Prereqs:** none

### 2013_etap1_2 (Telescoping sum impossibility)
- **Skills needed:** Algebraic manipulation, telescoping sums
- **Skills gained:** Recognizing impossible algebraic constraints
- **Prereqs:** none

### 2013_etap1_3 (Equilateral triangle midpoint)
- **Skills needed:** Equilateral triangle properties, angle chasing
- **Skills gained:** Complex equilateral triangle relationships
- **Prereqs:** 2011_etap1_2

### 2013_etap1_4 (Coupled quadratic system)
- **Skills needed:** System of equations, quadratic solving
- **Skills gained:** Solving coupled quadratic systems
- **Prereqs:** 2010_etap1_1

### 2013_etap1_5 (Area equality implies parallelism)
- **Skills needed:** Area relationships, trapezoid properties
- **Skills gained:** Using area equality to deduce geometry
- **Prereqs:** 2010_etap1_4

### 2013_etap1_6 (Sphere distance sum invariant)
- **Skills needed:** Sphere geometry, distance formula
- **Skills gained:** Distance-sum invariance on spheres
- **Prereqs:** 2010_etap1_5

### 2013_etap1_7 (Tiling with divisibility by 3)
- **Skills needed:** Tiling, parity, divisibility
- **Skills gained:** Divisibility constraints in tiling
- **Prereqs:** 2010_etap1_5

### 2013_etap2_1 (Nested square root equation)
- **Skills needed:** Square roots, perfect square analysis
- **Skills gained:** Analyzing nested square root equations
- **Prereqs:** 2011_etap1_6

### 2013_etap2_2 (Trapezoid median area)
- **Skills needed:** Trapezoid properties, median properties
- **Skills gained:** Using medians for area relationships
- **Prereqs:** 2013_etap1_5

### 2013_etap2_3 (Grid parity impossibility)
- **Skills needed:** Parity arguments, sum constraints
- **Skills gained:** Analyzing impossible sum configurations
- **Prereqs:** 2013_etap1_2

### 2013_etap2_4 (Colored convex points - special triangle)
- **Skills needed:** Graph theory, convex position, extremal arguments
- **Skills gained:** Finding triangular configurations in colored sets
- **Prereqs:** none

### 2013_etap2_5 (Midpoint angle equality)
- **Skills needed:** Midpoint geometry, angle relationships
- **Skills gained:** Complex angle-equality implications
- **Prereqs:** 2011_etap1_2

---

## Year 2014

### 2014_etap1_1 (Coin problem - linear Diophantine)
- **Skills needed:** Linear Diophantine equations, enumeration
- **Skills gained:** Solving constrained coin problems
- **Prereqs:** none

### 2014_etap1_2 (Circle reflection collinearity)
- **Skills needed:** Circle geometry, reflection symmetry
- **Skills gained:** Using symmetry for collinearity
- **Prereqs:** none

### 2014_etap1_3 (AM-GM optimization)
- **Skills needed:** AM-GM inequality, optimization
- **Skills gained:** Finding minima using AM-GM
- **Prereqs:** 2010_etap1_3

### 2014_etap1_4 (Regular graph degree changes)
- **Skills needed:** Graph theory, handshaking lemma
- **Skills gained:** Analyzing graph degree changes
- **Prereqs:** 2011_etap2_2

### 2014_etap1_5 (Reflection optimization)
- **Skills needed:** Reflection, locus problems
- **Skills gained:** Using reflection for optimization
- **Prereqs:** 2014_etap1_2

### 2014_etap1_6 (Tiling area parity)
- **Skills needed:** Area arguments, tiling constraints
- **Skills gained:** Area-based parity in tiling
- **Prereqs:** 2013_etap1_7

### 2014_etap1_7 (Tetrahedron distance bound)
- **Skills needed:** 3D geometry, Pythagorean theorem
- **Skills gained:** Distance bounds in tetrahedra
- **Prereqs:** none

### 2014_etap2_1 (Symmetric product-sum system)
- **Skills needed:** Symmetric equations, algebraic identities
- **Skills gained:** Solving symmetric systems with products
- **Prereqs:** 2011_etap2_4

### 2014_etap2_2 (Circle bisector intersection)
- **Skills needed:** Circle geometry, perpendicular bisectors
- **Skills gained:** Understanding bisector intersection properties
- **Prereqs:** 2011_etap2_5

### 2014_etap2_3 (Edge sum parity)
- **Skills needed:** Parity arguments, edge-sum analysis
- **Skills gained:** Counting parities in edge sums
- **Prereqs:** 2013_etap2_3

### 2014_etap2_4 (Prime arithmetic progression)
- **Skills needed:** Arithmetic progressions, prime properties
- **Skills gained:** Analyzing prime arithmetic progressions
- **Prereqs:** 2012_etap1_1

### 2014_etap2_5 (Equilateral triangle cevian areas)
- **Skills needed:** Equilateral triangle, cevians, area distribution
- **Skills gained:** Complex area configurations with cevians
- **Prereqs:** 2013_etap1_3

---

## Year 2015

### 2015_etap1_1 (Linear Diophantine with factoring)
- **Skills needed:** Algebraic manipulation, factorizations of 6
- **Skills gained:** Solving constrained equations
- **Prereqs:** none

### 2015_etap1_2 (Square with distance/angle constraints)
- **Skills needed:** Square properties, coordinate geometry
- **Skills gained:** Using constraints in squares
- **Prereqs:** none

### 2015_etap1_3 (Sophie Germain identity - n⁴+4)
- **Skills needed:** Sophie Germain identity, factorization
- **Skills gained:** Special factorizations for primality
- **Prereqs:** none (foundational for special factorizations)

### 2015_etap1_4 (Arc midpoint and incircle)
- **Skills needed:** Circle theorems, tangent properties
- **Skills gained:** Arc midpoint and incircle relationships
- **Prereqs:** none

### 2015_etap1_5 (Parity in cyclic arrangement)
- **Skills needed:** Parity arguments, modular arithmetic
- **Skills gained:** Using parity in cyclic configurations
- **Prereqs:** none

### 2015_etap1_6 (Divisibility with primes p(p+1))
- **Skills needed:** Divisibility, prime factorization
- **Skills gained:** Advanced divisibility with primes
- **Prereqs:** 2015_etap1_3

### 2015_etap1_7 (Pyramid distance constraints)
- **Skills needed:** 3D geometry, distance formulas
- **Skills gained:** Pyramid configurations with distance constraints
- **Prereqs:** none

### 2015_etap2_1 (System with primality constraints)
- **Skills needed:** Primality testing, small cases
- **Skills gained:** Systems with multiple prime constraints
- **Prereqs:** none

### 2015_etap2_2 (Parallelogram congruence)
- **Skills needed:** Parallelogram properties, congruent triangles
- **Skills gained:** Symmetry and congruence in parallelograms
- **Prereqs:** none

### 2015_etap2_3 (a+b=cd, c+d=ab inequality)
- **Skills needed:** Algebraic manipulation, AM-GM
- **Skills gained:** Proving non-negativity from constraints
- **Prereqs:** 2015_etap1_1

### 2015_etap2_4 (Triangle isosceles or right)
- **Skills needed:** Triangle analysis, case work
- **Skills gained:** Proving disjunctive conclusions
- **Prereqs:** none

### 2015_etap2_5 (100-gon balanced partition)
- **Skills needed:** Regular polygon symmetry, matching
- **Skills gained:** Balanced partitions using symmetry
- **Prereqs:** none

---

## Year 2016

### 2016_etap1_1 ((a+b+c)(a+b-c)=c² implies all zero)
- **Skills needed:** Algebraic manipulation, rationality
- **Skills gained:** Proving variables zero from single equation
- **Prereqs:** none

### 2016_etap1_2 (Circumcenter with external squares)
- **Skills needed:** Circumcenter properties, square constructions
- **Skills gained:** Relating external squares to circumcenter
- **Prereqs:** 2015_etap1_4

### 2016_etap1_3 (Sum constraint minimization)
- **Skills needed:** Extremal principle, constructive examples
- **Skills gained:** Optimizing under linear constraints
- **Prereqs:** none

### 2016_etap1_4 (Cyclic quadrilateral isosceles)
- **Skills needed:** Cyclic quadrilateral, inscribed angle theorem
- **Skills gained:** Combining inscribed angles with isosceles
- **Prereqs:** 2015_etap1_4

### 2016_etap1_5 (Difference of squares - parity cases)
- **Skills needed:** Parity analysis, difference of squares
- **Skills gained:** Case analysis based on parity
- **Prereqs:** 2015_etap1_5

### 2016_etap1_6 (3D pyramid with perpendicular edges)
- **Skills needed:** 3D geometry, Pythagorean theorem, volume
- **Skills gained:** Pyramid heights with perpendicular conditions
- **Prereqs:** 2015_etap1_7

### 2016_etap1_7 (Prime divides 4ab-1 with a+b+1)
- **Skills needed:** Divisibility with primes, modular analysis
- **Skills gained:** Using prime divisibility for equality
- **Prereqs:** 2015_etap1_6

### 2016_etap2_1 (Powers of 2 in array)
- **Skills needed:** Powers of 2, constructive examples
- **Skills gained:** Working with power constraints
- **Prereqs:** none

### 2016_etap2_2 (Trapezoid with perpendicular diagonals)
- **Skills needed:** Trapezoid, Pythagorean theorem
- **Skills gained:** Proving inequalities with perpendicular diagonals
- **Prereqs:** none

### 2016_etap2_3 (d|a+b, d²|ab implies d|a,d|b)
- **Skills needed:** GCD properties, divisibility theory
- **Skills gained:** Using divisibility constraints
- **Prereqs:** 2016_etap1_7

### 2016_etap2_4 (Sum with √2 coefficients)
- **Skills needed:** Algebraic manipulation, irrational parts
- **Skills gained:** Working with sums involving √2
- **Prereqs:** none

### 2016_etap2_5 (Euler's formula with angle constraints)
- **Skills needed:** Euler's formula, angle sum constraints
- **Skills gained:** Euler's formula with geometric constraints
- **Prereqs:** none

---

## Year 2017

### 2017_etap1_1 (3a+4b=3c, 4a-3b=4c Pythagorean)
- **Skills needed:** System solving, Pythagorean verification
- **Skills gained:** Recognizing Pythagorean from linear equations
- **Prereqs:** none

### 2017_etap1_2 (Parallelogram perpendicularity)
- **Skills needed:** Parallelogram properties, perpendicularity
- **Skills gained:** Distance constraints establishing perpendicularity
- **Prereqs:** 2015_etap2_2

### 2017_etap1_3 (Primes > 3 difference divisible by 48)
- **Skills needed:** Modular arithmetic, prime properties
- **Skills gained:** Divisibility by products using mod 6
- **Prereqs:** none

### 2017_etap1_4 (Trapezoid perpendicular bisector)
- **Skills needed:** Trapezoid, perpendicular bisectors
- **Skills gained:** Using bisectors in trapezoids
- **Prereqs:** none

### 2017_etap1_5 (3-coloring integers with sum constraint)
- **Skills needed:** Logical reasoning, coloring schemes
- **Skills gained:** Designing 3-colorings for integers
- **Prereqs:** none

### 2017_etap1_6 (m²+n=k(k+1) inequality)
- **Skills needed:** Algebraic manipulation, inequalities
- **Skills gained:** Deriving inequalities from equations
- **Prereqs:** none

### 2017_etap1_7 (Plane cutting cube into equal volumes)
- **Skills needed:** 3D coordinate geometry, plane equations
- **Skills gained:** Computing volumes cut by planes
- **Prereqs:** 2016_etap1_6

### 2017_etap2_1 ((a+x)²+(b+x)²=(c+x)² - no solution)
- **Skills needed:** Pythagorean triples, algebraic analysis
- **Skills gained:** Analyzing Pythagorean compatibility
- **Prereqs:** 2017_etap1_1

### 2017_etap2_2 (Circumcenter-altitude area relationship)
- **Skills needed:** Circumcenter, altitude properties
- **Skills gained:** Relating areas using circumcenter
- **Prereqs:** 2016_etap1_2

### 2017_etap2_3 (Integer system with substitution)
- **Skills needed:** System solving, integer constraints
- **Skills gained:** Finding all integer solutions
- **Prereqs:** 2015_etap1_1

### 2017_etap2_4 (Trapezoid symmetric angles)
- **Skills needed:** Cyclic quadrilateral, angle chasing
- **Skills gained:** Symmetric angle relationships in trapezoids
- **Prereqs:** 2017_etap1_4

### 2017_etap2_5 (Pigeonhole - same color difference is square)
- **Skills needed:** Pigeonhole principle, coloring
- **Skills gained:** Pigeonhole in coloring problems
- **Prereqs:** 2015_etap1_5

---

## Year 2018

### 2018_etap1_1 (999^1000 last digit)
- **Skills needed:** Modular arithmetic (mod 10), powers
- **Skills gained:** Computing last digits
- **Prereqs:** none

### 2018_etap1_2 (Quadrilateral with Law of Cosines)
- **Skills needed:** Law of cosines, coordinate geometry
- **Skills gained:** Computing lengths with angle constraints
- **Prereqs:** none

### 2018_etap1_3 (Inequality from rational equation)
- **Skills needed:** Algebraic manipulation, integer inequalities
- **Skills gained:** Deriving inequalities from equations
- **Prereqs:** 2017_etap1_6

### 2018_etap1_4 (Remainder constraints a≡2(b), b≡2(c), c≡4(a))
- **Skills needed:** Modular arithmetic, case analysis
- **Skills gained:** Solving constraint systems with remainders
- **Prereqs:** 2018_etap1_1

### 2018_etap1_5 (Parallelogram with equal lengths)
- **Skills needed:** Parallelogram, midpoint theorems
- **Skills gained:** Using equal lengths for perpendicularity
- **Prereqs:** 2017_etap1_2

### 2018_etap1_6 (Checkerboard selection)
- **Skills needed:** Checkerboard coloring, matching
- **Skills gained:** Selection problems on patterns
- **Prereqs:** none

### 2018_etap1_7 (Plane-cube intersection pyramid volume)
- **Skills needed:** 3D geometry, plane-cube intersection
- **Skills gained:** Finding plane intersections with cubes
- **Prereqs:** 2017_etap1_7

### 2018_etap2_1 (f(x)=x²+x inequality)
- **Skills needed:** Quadratic function properties
- **Skills gained:** Proving inequalities using function properties
- **Prereqs:** none

### 2018_etap2_2 (Trapezoid with angle bisector)
- **Skills needed:** Trapezoid, angle bisectors
- **Skills gained:** Using angle bisectors for area relationships
- **Prereqs:** 2017_etap2_4

### 2018_etap2_3 (Regular polygon - even intersections)
- **Skills needed:** Parity arguments, line intersections
- **Skills gained:** Proving parity of intersections
- **Prereqs:** 2015_etap2_5

### 2018_etap2_4 (Equal divisions with perpendicularity)
- **Skills needed:** Triangle geometry, midpoint properties
- **Skills gained:** Using equal divisions for perpendicularity
- **Prereqs:** 2018_etap1_5

### 2018_etap2_5 (Number without digits 1,2,9 times 3)
- **Skills needed:** Digit analysis, modular arithmetic
- **Skills gained:** Analyzing digit constraints under multiplication
- **Prereqs:** 2018_etap1_1

---

## Year 2019

### 2019_etap1_1 (Appending digit gives 13n)
- **Skills needed:** Place value, linear equations
- **Skills gained:** Solving digit-appending problems
- **Prereqs:** none

### 2019_etap1_2 (Chain of equal segments)
- **Skills needed:** Isosceles triangles, angle chasing
- **Skills gained:** Working with chains of equal segments
- **Prereqs:** none

### 2019_etap1_3 (Symmetric product equations)
- **Skills needed:** Symmetric equations, case analysis
- **Skills gained:** Solving symmetric systems with products
- **Prereqs:** 2015_etap2_3

### 2019_etap1_4 (Rectangle with 45° angle - equal areas)
- **Skills needed:** Area formulas, angle constraints
- **Skills gained:** Using constraints for area equality
- **Prereqs:** none

### 2019_etap1_5 (Tournament with minimum draws)
- **Skills needed:** Graph theory, tournament theory
- **Skills gained:** Minimizing draws in balanced tournaments
- **Prereqs:** none

### 2019_etap1_6 (Digit sum impossibility)
- **Skills needed:** Digit analysis, divisibility by 3
- **Skills gained:** Analyzing digit sum constraints
- **Prereqs:** none

### 2019_etap1_7 (Rhombus prism - square cross-section)
- **Skills needed:** 3D geometry, rhombus properties
- **Skills gained:** Finding square cross-sections in prisms
- **Prereqs:** 2017_etap1_7

### 2019_etap2_1 (Consecutive sums imply integer)
- **Skills needed:** Consecutive integers, parity
- **Skills gained:** Proving integer properties from sum constraints
- **Prereqs:** none

### 2019_etap2_2 (Parallelogram bisector intersection)
- **Skills needed:** Parallelogram, perpendicular bisectors
- **Skills gained:** Bisector intersections and side lengths
- **Prereqs:** 2017_etap1_2

### 2019_etap2_3 (Tournament with gender constraints)
- **Skills needed:** Pigeonhole, tournament theory
- **Skills gained:** Analyzing tournaments with constraints
- **Prereqs:** 2019_etap1_5

### 2019_etap2_4 (Triangle with 45° and obtuse angle)
- **Skills needed:** Triangle inequalities, trigonometry
- **Skills gained:** Proving strict inequalities with √2
- **Prereqs:** none

### 2019_etap2_5 (gcd(a+n,b+n)>1 for all n implies a=b)
- **Skills needed:** GCD properties, proof by contradiction
- **Skills gained:** Using GCD invariance for equality
- **Prereqs:** 2016_etap2_3

---

## Year 2020

### 2020_etap1_1 (Six-digit with 2-digit squares)
- **Skills needed:** Pattern recognition, enumeration
- **Skills gained:** Constraint-based search
- **Prereqs:** none

### 2020_etap1_2 (Isosceles triangle altitudes)
- **Skills needed:** Triangle altitudes, Pythagorean theorem
- **Skills gained:** Relating altitudes in isosceles triangles
- **Prereqs:** none (foundational for geometry 2020s)

### 2020_etap1_3 (|a-b|=2|b-c|=3|c-a|)
- **Skills needed:** Absolute value manipulation, case analysis
- **Skills gained:** Case analysis with absolute values
- **Prereqs:** none

### 2020_etap1_4 (Quadrilateral with 120° angles)
- **Skills needed:** Law of cosines, angle chasing
- **Skills gained:** Solving quadrilaterals with given angles
- **Prereqs:** none

### 2020_etap1_5 (Sum=2^1002, product=5^1002 impossible)
- **Skills needed:** Prime factorization, impossibility proofs
- **Skills gained:** Impossibility using prime constraints
- **Prereqs:** none

### 2020_etap1_6 (Polygon diagonal parity)
- **Skills needed:** Parity arguments, pigeonhole
- **Skills gained:** Using parity for existence
- **Prereqs:** none

### 2020_etap1_7 (Pentagon folding into 3D)
- **Skills needed:** Regular pentagon, 3D spatial reasoning
- **Skills gained:** Complex spatial visualization
- **Prereqs:** none (foundational for folding problems)

### 2020_etap2_1 (2a+a²=2b+b² integrality)
- **Skills needed:** Factorization, completing the square
- **Skills gained:** Integrality preservation in quadratics
- **Prereqs:** none

### 2020_etap2_2 (Square diagonal point - right angle)
- **Skills needed:** Square symmetry, congruent triangles
- **Skills gained:** Using equal sides for right angles
- **Prereqs:** 2020_etap1_2

### 2020_etap2_3 (5a+3b divisible by a+b implies a=b)
- **Skills needed:** Divisibility arguments, linear combinations
- **Skills gained:** Proving equality from divisibility
- **Prereqs:** none

### 2020_etap2_4 (Parallelogram angle bisector perpendicularity)
- **Skills needed:** Parallelogram, angle bisector theorem
- **Skills gained:** Relating sides to bisector perpendicularity
- **Prereqs:** none

### 2020_etap2_5 (Birthday party - someone knows all)
- **Skills needed:** Graph theory, extremal arguments
- **Skills gained:** Finding maximum degree vertices
- **Prereqs:** none

---

## Year 2021

### 2021_etap1_1 (Test score from averages)
- **Skills needed:** Average calculations, linear equations
- **Skills gained:** Relating individual to group averages
- **Prereqs:** none

### 2021_etap1_2 (Rectangle with AB=BX=XD)
- **Skills needed:** Isosceles triangles, angle calculation
- **Skills gained:** Using equal distances for angles
- **Prereqs:** none

### 2021_etap1_3 (Integer between √(2n) and √(5n))
- **Skills needed:** Function growth, existence proofs
- **Skills gained:** Existence proofs using intervals
- **Prereqs:** none

### 2021_etap1_4 (Table 1-17 with sum constraints)
- **Skills needed:** Parity, sum constraints
- **Skills gained:** Determining impossible configurations
- **Prereqs:** none

### 2021_etap1_5 (Equilateral triangle with K,L,M)
- **Skills needed:** Equilateral triangle, perpendicularity
- **Skills gained:** Complex angle chasing in equilateral triangles
- **Prereqs:** 2021_etap1_2

### 2021_etap1_6 (10×10 arrow board - remove half)
- **Skills needed:** Matching theory, bipartite structure
- **Skills gained:** Removing to break mutual relationships
- **Prereqs:** none

### 2021_etap1_7 (All permutations divisible by 7)
- **Skills needed:** Divisibility by 7, permutation properties
- **Skills gained:** Using divisibility across permutations
- **Prereqs:** none

### 2021_etap2_1 (Perpendicular segments AB, CD)
- **Skills needed:** Coordinate geometry, Pythagorean theorem
- **Skills gained:** Using perpendicularity for lengths
- **Prereqs:** 2020_etap1_2

### 2021_etap2_2 (Divisors a,b with a+b=ab/n)
- **Skills needed:** Divisibility, algebraic manipulation
- **Skills gained:** Proving divisor equality
- **Prereqs:** 2020_etap2_3

### 2021_etap2_3 (Coloring 1-100 - min colors)
- **Skills needed:** Modular arithmetic, pigeonhole
- **Skills gained:** Minimizing colors under divisibility
- **Prereqs:** none

### 2021_etap2_4 (Convex pentagon area equality)
- **Skills needed:** Pentagon area decomposition
- **Skills gained:** Proving equal areas with constraints
- **Prereqs:** none

### 2021_etap2_5 (Points on line - even distance sums)
- **Skills needed:** Parity arguments, distance sums
- **Skills gained:** Proving all distances even
- **Prereqs:** 2020_etap1_6

---

## Year 2022

### 2022_etap1_1 (Rectangle perimeter=area=x)
- **Skills needed:** Rectangle formulas, quadratic equations
- **Skills gained:** Setting up geometric optimization
- **Prereqs:** none

### 2022_etap1_2 (Alternating sum 1-2+3-4+...-100)
- **Skills needed:** Arithmetic series, pattern recognition
- **Skills gained:** Finding partial sums in alternating series
- **Prereqs:** none

### 2022_etap1_3 (Rectangle with E,F - equal areas)
- **Skills needed:** Triangle areas, decomposition
- **Skills gained:** Proving area equality through decomposition
- **Prereqs:** 2021_etap2_4

### 2022_etap1_4 (Coloring 1-n with bijection)
- **Skills needed:** Set theory, bijection properties
- **Skills gained:** Finding minimal configurations
- **Prereqs:** none

### 2022_etap1_5 (a+b+c ≥ ¾abc inequality)
- **Skills needed:** AM-GM, inequality chaining
- **Skills gained:** Combining multiple inequalities
- **Prereqs:** none

### 2022_etap1_6 (n×n square with +-  tiling impossibility)
- **Skills needed:** Tiling arguments, area parity
- **Skills gained:** Impossibility using area modulo arguments
- **Prereqs:** none

### 2022_etap1_7 (Regular hexagon folding - tetrahedron volume)
- **Skills needed:** Regular hexagon, 3D folding
- **Skills gained:** Computing volumes of folded polygons
- **Prereqs:** 2020_etap1_7

### 2022_etap2_1 (D,E on triangle sides - angle equality)
- **Skills needed:** Angle chasing, isosceles triangles
- **Skills gained:** Using angle equalities for side equalities
- **Prereqs:** 2021_etap1_5

### 2022_etap2_2 (2,5 on board - GCD invariant)
- **Skills needed:** Linear Diophantine, GCD invariants
- **Skills gained:** Proving impossibility using GCD
- **Prereqs:** none

### 2022_etap2_3 (Insert digit - 6n)
- **Skills needed:** Decimal representation, modular arithmetic
- **Skills gained:** Solving digit insertion problems
- **Prereqs:** none

### 2022_etap2_4 (Parallelogram with X,Y - equal AC)
- **Skills needed:** Parallelogram, congruent triangles
- **Skills gained:** Using multiple equal constraints
- **Prereqs:** 2020_etap2_4

### 2022_etap2_5 (4×4 table - pigeonhole)
- **Skills needed:** Pigeonhole principle, row sums
- **Skills gained:** Proving collisions in limited space
- **Prereqs:** none

---

## Year 2023

### 2023_etap1_1 (11...199...9 primality)
- **Skills needed:** Divisibility by 11, primality
- **Skills gained:** Using divisibility rules for special forms
- **Prereqs:** none

### 2023_etap1_2 (X,Y on triangle with equal distances)
- **Skills needed:** Isosceles triangles, angle calculation
- **Skills gained:** Angles from equal length constraints
- **Prereqs:** 2021_etap1_2

### 2023_etap1_3 (Matchstick digits - max sum)
- **Skills needed:** Optimization, digit representations
- **Skills gained:** Maximizing digits with constraints
- **Prereqs:** none

### 2023_etap1_4 (Difference of cubes is prime)
- **Skills needed:** Difference of cubes, prime factorization
- **Skills gained:** Factoring special forms for primes
- **Prereqs:** none

### 2023_etap1_5 (Three concentric circles)
- **Skills needed:** Circle areas, Pythagorean theorem
- **Skills gained:** Relating concentric circle areas
- **Prereqs:** 2020_etap1_2

### 2023_etap1_6 (ab+b+1, bc+c+1, ca+a+1 cyclic)
- **Skills needed:** Algebraic manipulation, symmetric expressions
- **Skills gained:** Proving cyclic implications
- **Prereqs:** none

### 2023_etap1_7 (Diagram 11-29 - sum constraints)
- **Skills needed:** Graph coloring, sum constraints
- **Skills gained:** Proving impossibility via parity
- **Prereqs:** 2021_etap1_4

### 2023_etap2_1 (Consecutive products - perfect square)
- **Skills needed:** Consecutive integers, perfect squares
- **Skills gained:** Proving one of two is perfect square
- **Prereqs:** none

### 2023_etap2_2 (6×6 square - duplicate rectangle areas)
- **Skills needed:** Pigeonhole, rectangle areas
- **Skills gained:** Proving duplicate areas
- **Prereqs:** 2022_etap2_5

### 2023_etap2_3 (Trapezoid with P on AC)
- **Skills needed:** Trapezoid angles, angle chasing
- **Skills gained:** Using multiple angles for length equality
- **Prereqs:** 2022_etap2_1

### 2023_etap2_4 (Square divided - equal parts imply)
- **Skills needed:** Square area decomposition
- **Skills gained:** Proving partition implications
- **Prereqs:** 2022_etap1_3

### 2023_etap2_5 (800 numbers - balanced subset)
- **Skills needed:** Pigeonhole, subset sums
- **Skills gained:** Finding balanced subsets
- **Prereqs:** 2021_etap2_3

---

## Year 2024

### 2024_etap1_1 (Point in square - consecutive distances)
- **Skills needed:** Geometric constraints, integer solutions
- **Skills gained:** Checking distance feasibility
- **Prereqs:** none

### 2024_etap1_2 (Rhombus folding)
- **Skills needed:** Rhombus properties, paper folding
- **Skills gained:** Fold-induced equidistance
- **Prereqs:** 2020_etap1_7

### 2024_etap1_3 (|b-c|, |c-a|, |a-b| between 1 and 2)
- **Skills needed:** Triangle inequality, absolute values
- **Skills gained:** Proving impossibility via inequality chains
- **Prereqs:** 2020_etap1_3

### 2024_etap1_4 (Red and blue stones - balanced removal)
- **Skills needed:** Greedy algorithms, interval selection
- **Skills gained:** Balanced removals preserving separation
- **Prereqs:** none

### 2024_etap1_5 (Five expressions all prime - 3|b)
- **Skills needed:** Prime properties, divisibility by 3
- **Skills gained:** Using multiple prime constraints
- **Prereqs:** none

### 2024_etap1_6 (Staircase diagram - distinct sums)
- **Skills needed:** Parity arguments, row/column sums
- **Skills gained:** Finding n where distinct sums possible
- **Prereqs:** 2023_etap1_7

### 2024_etap1_7 (Box with AC'=AB+AD - perpendicularity)
- **Skills needed:** 3D geometry, Pythagorean theorem
- **Skills gained:** Proving perpendicularity from distances
- **Prereqs:** 2020_etap1_2

### 2024_etap2_1 (Rectangle with E on CD - angle inequality)
- **Skills needed:** Rectangle angles, angle inequalities
- **Skills gained:** Using angle sums for side inequalities
- **Prereqs:** 2022_etap2_1

### 2024_etap2_2 (5×5 table coloring - unique)
- **Skills needed:** Counting arguments, constraint satisfaction
- **Skills gained:** Determining unique configurations
- **Prereqs:** 2021_etap1_4

### 2024_etap2_3 (Isosceles with 150° - triangle type)
- **Skills needed:** Isosceles triangles, reflection
- **Skills gained:** Proving triangle type from reflections
- **Prereqs:** 2021_etap1_5

### 2024_etap2_4 (Cube roots sum = ³√2025 - no solution)
- **Skills needed:** Cube roots, Diophantine equations
- **Skills gained:** Irrationality contradictions
- **Prereqs:** none

### 2024_etap2_5 (Olympic numbers - squaring preserves)
- **Skills needed:** Recursive sequences, invariants
- **Skills gained:** Proving closure under squaring
- **Prereqs:** 2022_etap2_2

---

## Year 2025

### 2025_etap1_1 (2zł and 5zł coins - exactly 50)
- **Skills needed:** Linear Diophantine, greedy algorithms
- **Skills gained:** Finding subset sums
- **Prereqs:** none

### 2025_etap1_2 (n = 21 × digit_sum)
- **Skills needed:** Divisibility by 9, digit sum properties
- **Skills gained:** Using digit sum divisibility rules
- **Prereqs:** none

### 2025_etap1_3 (5 people friendship degrees)
- **Skills needed:** Graph theory, degree sequences
- **Skills gained:** Determining valid degree sequences
- **Prereqs:** none

### 2025_etap1_4 ((a+b²)(a³+b³)=a⁴+b⁵)
- **Skills needed:** Polynomial expansion, sign analysis
- **Skills gained:** Proving sign constraints from equations
- **Prereqs:** 2023_etap1_6

### 2025_etap1_5 (Trapezoid ABCD with P)
- **Skills needed:** Trapezoid, isosceles triangles
- **Skills gained:** Finding angles from multiple constraints
- **Prereqs:** 2023_etap2_3

### 2025_etap1_6 (2n is cube, 3n is square)
- **Skills needed:** Prime factorization, perfect powers
- **Skills gained:** Using factorization for divisibility
- **Prereqs:** none

### 2025_etap1_7 (Triangle with angle sides)
- **Skills needed:** Triangle inequality, angle sums
- **Skills gained:** Proving triangle existence from angles
- **Prereqs:** none

---

## Key Prerequisite Chains Summary

### Pigeonhole Principle Chain
- 2005_etap1_3 (basic geometric) → 2005_etap2_2 (with modular arithmetic) → 2006_etap1_7 (advanced geometric) → 2007_etap2_2 (bounded sums) → 2009_etap1_5 (with quadratic residues)

### Number Theory/Modular Arithmetic Chain
- 2006_etap1_1 (digit sums) → 2007_etap1_4 (cyclic divisibility) → 2018_etap1_1 (powers mod 10)
- 2005_etap2_4 (primality testing) → 2006_etap1_3 (prime triples) → 2008_etap1_4 (prime + divisibility) → 2009_etap2_3 (consecutive quadratics)

### Symmetric Systems Chain
- 2005_etap1_4 → 2008_etap2_1 → 2010_etap1_1 → 2011_etap2_4 → 2014_etap2_1

### Geometry - Circle/Cyclic Quadrilateral Chain
- 2005_etap1_2 (tangential) → 2007_etap1_5 (angle constraints) → 2010_etap1_6 → 2011_etap2_5 → 2014_etap2_2 → 2015_etap1_4 → 2016_etap1_2/2016_etap1_4

### 3D Geometry Chain
- 2005_etap2_1 (polyhedra basics) → 2008_etap1_7 (projections) → 2015_etap1_7 → 2016_etap1_6 → 2017_etap1_7 → 2018_etap1_7

### Invariants Chain
- 2010_etap1_5 (L-shaped pieces) → 2013_etap1_6 (sphere distances) → 2013_etap1_7 (tiling) → 2014_etap1_6

### Graph Theory Chain
- 2006_etap2_3 (edges/triangles) → 2009_etap2_4 (friendship graphs) → 2011_etap2_2 (parity) → 2012_etap1_4 → 2014_etap1_4

### Area Methods Chain
- 2010_etap1_4 (invariance) → 2010_etap2_1 → 2013_etap1_5 → 2013_etap2_2 → 2021_etap2_4 → 2022_etap1_3 → 2023_etap2_4

### Parallelogram/Trapezoid Chain
- 2015_etap2_2 → 2017_etap1_2 → 2018_etap1_5 → 2019_etap2_2 → 2020_etap2_4 → 2022_etap2_4

### Parity Arguments Chain
- 2015_etap1_5 → 2016_etap1_5 → 2017_etap2_5 → 2018_etap2_3 → 2020_etap1_6 → 2021_etap2_5

### Folding/Spatial Visualization Chain
- 2020_etap1_7 (pentagon folding) → 2022_etap1_7 (hexagon folding) → 2024_etap1_2 (rhombus folding)

---

## Notes for Manual Review

1. **Cross-year dependencies** - Many skills appear repeatedly across years. Consider adding dependencies to the earliest good examples.

2. **Difficulty progression** - Generally etap2 tasks should consider etap1 tasks from same or earlier years as prerequisites.

3. **Category alignment** - Tasks with same categories (algebra, geometry, etc.) often share techniques.

4. **Foundation tasks** - Tasks marked "none" for prereqs are good starting points for students.

5. **Skill clusters** - Some skills appear together (e.g., pigeonhole + modular arithmetic, AM-GM + optimization).

This file should be reviewed and curated before translating into the JSON structure. Focus on dependencies that represent genuine skill progression, not just topic similarity.
