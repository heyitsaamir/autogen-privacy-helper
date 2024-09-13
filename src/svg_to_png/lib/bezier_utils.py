import math


def solve_quadratic(a, b, c):
    """Solves a quadratic equation a*t^2 + b*t + c = 0 and returns real roots."""
    if a == 0:
        if b == 0:
            return []  # No solution if both a and b are 0
        return [-c / b]  # Linear solution if a is 0
    discriminant = b**2 - 4 * a * c
    if discriminant < 0:
        return []  # No real solutions
    elif discriminant == 0:
        return [-b / (2 * a)]  # One real solution
    else:
        sqrt_discriminant = math.sqrt(discriminant)
        t1 = (-b + sqrt_discriminant) / (2 * a)
        t2 = (-b - sqrt_discriminant) / (2 * a)
        return [t1, t2]  # Two real solutions

def bezier_curve_point(t, sourceX, sourceY, controlX, controlY, targetX, targetY):
    """
    Calculates the (x, y) coordinates of a quadratic Bézier curve at parameter t.
    """
    x = (1 - t)**2 * sourceX + 2 * (1 - t) * t * controlX + t**2 * targetX
    y = (1 - t)**2 * sourceY + 2 * (1 - t) * t * controlY + t**2 * targetY
    return x, y

def find_bezier_points_for_x_or_y(x_p, y_p, sourceX, sourceY, controlX, controlY, targetX, targetY, check_for_x=True):
    """
    Finds the t values and the corresponding points (x, y) for which the Bezier curve 
    has the same x or y coordinate as the given point.

    Parameters:
    x_p, y_p: Coordinates of the point.
    sourceX, sourceY: Source point of the Bezier curve.
    controlX, controlY: Control point of the Bezier curve.
    targetX, targetY: Target point of the Bezier curve.
    check_for_x: If True, solve for x. If False, solve for y.

    Returns:
    A list of tuples (t, (x, y)) where t is the parameter and (x, y) is the point on the curve.
    """
    if check_for_x:
        # Quadratic coefficients for x
        a = sourceX - 2 * controlX + targetX
        b = -2 * sourceX + 2 * controlX
        c = sourceX - x_p
    else:
        # Quadratic coefficients for y
        a = sourceY - 2 * controlY + targetY
        b = -2 * sourceY + 2 * controlY
        c = sourceY - y_p
    
    # Solve the quadratic equation to find t values
    t_values = solve_quadratic(a, b, c)

    # Filter valid t values (0 <= t <= 1)
    valid_t_values = [t for t in t_values if 0 <= t <= 1]

    # Calculate the corresponding points on the curve for each valid t
    points_on_curve = []
    for t in valid_t_values:
        x, y = bezier_curve_point(t, sourceX, sourceY, controlX, controlY, targetX, targetY)
        points_on_curve.append((t, (x, y)))

    return points_on_curve

# Whether two points are on the same side of a line
def is_on_same_side(x1, y1, x2, y2, line_x1, line_y1, line_x2, line_y2):
    def sign(x, y, line_x1, line_y1, line_x2, line_y2):
        return (x - line_x2) * (line_y1 - line_y2) - (line_x1 - line_x2) * (y - line_y2)

    d1 = sign(x1, y1, line_x1, line_y1, line_x2, line_y2)
    d2 = sign(x2, y2, line_x1, line_y1, line_x2, line_y2)

    return d1 * d2 >= 0

# Whether a point is on the inner side of a Bézier curve (in the convex hull)
def is_on_inner_side_of_bezier(sourceX, sourceY, controlX, controlY, targetX, targetY, x_p, y_p):
    points_for_x = find_bezier_points_for_x_or_y(x_p, y_p, sourceX, sourceY, controlX, controlY, targetX, targetY, check_for_x=True)
    if len(points_for_x) == 2:
        y1 = points_for_x[0][1][1]
        y2 = points_for_x[1][1][1]
        return min(y1, y2) <= y_p <= max(y1, y2)
            
    # Find points on the curve where y = y_p
    points_for_y = find_bezier_points_for_x_or_y(x_p, y_p, sourceX, sourceY, controlX, controlY, targetX, targetY, check_for_x=False)
    if len(points_for_y) == 2:
        x1 = points_for_y[0][1][0]
        x2 = points_for_y[1][1][0]
        return min(x1, x2) <= x_p <= max(x1, x2)
    
    if len(points_for_x) == 1 and len(points_for_y) == 1:
        return not is_on_same_side(x_p, y_p, controlX, controlY, points_for_x[0][1][0], points_for_x[0][1][1], points_for_y[0][1][0], points_for_y[0][1][1])
    elif len(points_for_x) == 1 or len(points_for_y) == 1:
        x, y = points_for_x[0][1] if len(points_for_x) == 1 else points_for_y[0][1]
        return (is_on_same_side(x_p, y_p, x, y, sourceX, sourceY, controlX, controlY) and
                is_on_same_side(x_p, y_p, x, y, controlX, controlY, targetX, targetY) and
                not is_on_same_side(x_p, y_p, controlX, controlY, sourceX, sourceY, targetX, targetY))
    else:
        # Find the point on the curve where t is 0.5
        t = 0.5
        x, y = bezier_curve_point(t, sourceX, sourceY, controlX, controlY, targetX, targetY)
        return (is_on_same_side(x_p, y_p, x, y, sourceX, sourceY, controlX, controlY) and
                is_on_same_side(x_p, y_p, x, y, controlX, controlY, targetX, targetY)and
                not is_on_same_side(x_p, y_p, controlX, controlY, sourceX, sourceY, targetX, targetY))
