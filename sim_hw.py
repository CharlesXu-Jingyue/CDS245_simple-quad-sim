import scipy.spatial.transform
import numpy as np
from animate_function import QuadPlotter

# Quaternion multiplication function
def quat_mult(q, p):
    # q * p
    # p,q = [w x y z]
    return np.array(
        [
            p[0] * q[0] - q[1] * p[1] - q[2] * p[2] - q[3] * p[3],
            q[1] * p[0] + q[0] * p[1] + q[2] * p[3] - q[3] * p[2],
            q[2] * p[0] + q[0] * p[2] + q[3] * p[1] - q[1] * p[3],
            q[3] * p[0] + q[0] * p[3] + q[1] * p[2] - q[2] * p[1],
        ]
    )

# Quaternion conjugate function
def quat_conjugate(q):
    return np.array([q[0], -q[1], -q[2], -q[3]])

# Function to create a quaternion from two vectors
def quaternion_from_vectors(v_from, v_to):
    v_from = normalized(v_from)
    v_to = normalized(v_to)
    v_mid = normalized(v_from + v_to)
    q = np.array([np.dot(v_from, v_mid), *np.cross(v_from, v_mid)])
    return q

# Function to normalize a vector
def normalized(v):
    norm = np.linalg.norm(v)
    return v / norm

# Constants for state indices
NO_STATES = 13
IDX_POS_X = 0
IDX_POS_Y = 1
IDX_POS_Z = 2
IDX_VEL_X = 3
IDX_VEL_Y = 4
IDX_VEL_Z = 5
IDX_QUAT_W = 6
IDX_QUAT_X = 7
IDX_QUAT_Y = 8
IDX_QUAT_Z = 9
IDX_OMEGA_X = 10
IDX_OMEGA_Y = 11
IDX_OMEGA_Z = 12

# Robot class representing the quadcopter
class Robot:
    '''
    frames:
        B - body frame
        I - inertial frame
    states:
        p_I - position of the robot in the inertial frame (state[0], state[1], state[2])
        v_I - velocity of the robot in the inertial frame (state[3], state[4], state[5])
        q - orientation of the robot (w=state[6], x=state[7], y=state[8], z=state[9])
        omega - angular velocity of the robot (state[10], state[11], state[12])
    inputs:
        omega_1, omega_2, omega_3, omega_4 - angular velocities of the motors
    '''
    def __init__(self):
        self.m = 1.0 # mass of the robot
        self.arm_length = 0.25 # length of the quadcopter arm (motor to center)
        self.height = 0.05 # height of the quadcopter
        self.body_frame = np.array([(self.arm_length, 0, 0, 1),
                                    (0, self.arm_length, 0, 1),
                                    (-self.arm_length, 0, 0, 1),
                                    (0, -self.arm_length, 0, 1),
                                    (0, 0, 0, 1),
                                    (0, 0, self.height, 1)])

        self.J = 0.025 * np.eye(3) # Inertia matrix [kg m^2]
        self.J_inv = np.linalg.inv(self.J)
        self.constant_thrust = 10e-4
        self.constant_drag = 10e-6
        self.omega_motors = np.array([0.0, 0.0, 0.0, 0.0])
        self.state = self.reset_state_and_input(np.array([1.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0, 0.0]))
        self.time = 0.0

    # Function to reset the state and input
    def reset_state_and_input(self, init_xyz, init_quat_wxyz):
        state0 = np.zeros(NO_STATES)
        state0[IDX_POS_X:IDX_POS_Z+1] = init_xyz
        state0[IDX_VEL_X:IDX_VEL_Z+1] = np.array([0.0, 0.0, 0.0])
        state0[IDX_QUAT_W:IDX_QUAT_Z+1] = init_quat_wxyz
        state0[IDX_OMEGA_X:IDX_OMEGA_Z+1] = np.array([0.0, 0.0, 0.0])
        return state0

    # Function to update the state of the quadcopter
    def update(self, omegas_motor, dt):
        p_I = self.state[IDX_POS_X:IDX_POS_Z+1]
        v_I = self.state[IDX_VEL_X:IDX_VEL_Z+1]
        q = self.state[IDX_QUAT_W:IDX_QUAT_Z+1]
        omega = self.state[IDX_OMEGA_X:IDX_OMEGA_Z+1]
        R = scipy.spatial.transform.Rotation.from_quat([q[1], q[2], q[3], q[0]]).as_matrix()

        thrust = self.constant_thrust * np.sum(omegas_motor**2)
        f_b = np.array([0, 0, thrust])
        
        tau_x = self.constant_thrust * (omegas_motor[3]**2 - omegas_motor[1]**2) * 2 * self.arm_length
        tau_y = self.constant_thrust * (omegas_motor[2]**2 - omegas_motor[0]**2) * 2 * self.arm_length
        tau_z = self.constant_drag * (omegas_motor[0]**2 - omegas_motor[1]**2 + omegas_motor[2]**2 - omegas_motor[3]**2)
        tau_b = np.array([tau_x, tau_y, tau_z])

        v_dot = 1 / self.m * R @ f_b + np.array([0, 0, -9.81])

        omega_dot = self.J_inv @ (np.cross(self.J @ omega, omega) + tau_b)
        q_dot = 1 / 2 * quat_mult(q, [0, *omega])
        p_dot = v_I
        
        x_dot = np.concatenate([p_dot, v_dot, q_dot, omega_dot])
        self.state += x_dot * dt
        self.state[IDX_QUAT_W:IDX_QUAT_Z+1] /= np.linalg.norm(self.state[IDX_QUAT_W:IDX_QUAT_Z+1]) # Re-normalize quaternion.
        self.time += dt

    # Function to update the state of the quadcopter
    def update_wind(self, omegas_motor, dt):
        p_I = self.state[IDX_POS_X:IDX_POS_Z+1]
        v_I = self.state[IDX_VEL_X:IDX_VEL_Z+1]
        q = self.state[IDX_QUAT_W:IDX_QUAT_Z+1]
        omega = self.state[IDX_OMEGA_X:IDX_OMEGA_Z+1]
        R = scipy.spatial.transform.Rotation.from_quat([q[1], q[2], q[3], q[0]]).as_matrix()

        thrust = self.constant_thrust * np.sum(omegas_motor**2)
        f_b = np.array([0, 0, thrust])
        
        tau_x = self.constant_thrust * (omegas_motor[3]**2 - omegas_motor[1]**2) * 2 * self.arm_length
        tau_y = self.constant_thrust * (omegas_motor[2]**2 - omegas_motor[0]**2) * 2 * self.arm_length
        tau_z = self.constant_drag * (omegas_motor[0]**2 - omegas_motor[1]**2 + omegas_motor[2]**2 - omegas_motor[3]**2)
        tau_b = np.array([tau_x, tau_y, tau_z])

        # Compute the wind disturbance force
        # self.F0 = np.array([1.0, 0.0, 0.0])
        # self.omega_w = 2 * np.pi / 10
        self.phi = 0
        self.wind_force = self.F0 * np.sin(self.omega_w * self.time + self.phi)
        v_dot = 1 / self.m * (R @ f_b + self.wind_force) + np.array([0, 0, -9.81])

        omega_dot = self.J_inv @ (np.cross(self.J @ omega, omega) + tau_b)
        q_dot = 1 / 2 * quat_mult(q, [0, *omega])
        p_dot = v_I
        
        x_dot = np.concatenate([p_dot, v_dot, q_dot, omega_dot])
        self.state += x_dot * dt
        self.state[IDX_QUAT_W:IDX_QUAT_Z+1] /= np.linalg.norm(self.state[IDX_QUAT_W:IDX_QUAT_Z+1]) # Re-normalize quaternion.
        self.time += dt

    # Control function to compute the motor speeds
    def control(self, p_d_I):
        p_I = self.state[IDX_POS_X:IDX_POS_Z+1]
        v_I = self.state[IDX_VEL_X:IDX_VEL_Z+1]
        q = self.state[IDX_QUAT_W:IDX_QUAT_Z+1]
        omega_b = self.state[IDX_OMEGA_X:IDX_OMEGA_Z+1]

        # Position controller.
        k_p = 1.0
        k_d = 10.0
        v_r = - k_p * (p_I - p_d_I)
        a = -k_d * (v_I - v_r) + np.array([0, 0, 9.81])
        f = self.m * a
        f_b = scipy.spatial.transform.Rotation.from_quat([q[1], q[2], q[3], q[0]]).as_matrix().T @ f
        thrust = np.max([0, f_b[2]])
        
        # Attitude controller.
        q_ref = quaternion_from_vectors(np.array([0, 0, 1]), normalized(f))
        q_err = quat_mult(quat_conjugate(q_ref), q) # error from Body to Reference.
        if (q_err[0] < 0):
            q_err = -q_err
        k_q = 20.0
        k_omega = 100.0
        omega_ref = - k_q * 2 * q_err[1:]
        alpha = - k_omega * (omega_b - omega_ref)
        tau = self.J @ alpha + np.cross(omega_b, self.J @ omega_b)
        
        # Compute the motor speeds.
        B = np.array([
            [self.constant_thrust, self.constant_thrust, self.constant_thrust, self.constant_thrust],
            [0, -self.arm_length * self.constant_thrust, 0, self.arm_length * self.constant_thrust],
            [-self.arm_length * self.constant_thrust, 0, self.arm_length * self.constant_thrust, 0],
            [self.constant_drag, -self.constant_drag, self.constant_drag, -self.constant_drag]
        ])
        B_inv = np.linalg.inv(B)
        omega_motor_square = B_inv @ np.concatenate([np.array([thrust]), tau])
        omega_motor = np.sqrt(np.clip(omega_motor_square, 0, None))
        return omega_motor

# Constants for playback speed and control frequency
PLAYBACK_SPEED = 1
CONTROL_FREQUENCY = 200 # Hz for attitude control loop
dt = 1.0 / CONTROL_FREQUENCY
time = [0.0]

# Function to get the full position of the quadcopter
def get_pos_full_quadcopter(quad):
    """ position returns a 3 x 6 matrix 
        where row is [x, y, z] column is m1 m2 m3 m4 origin h
    """
    origin = quad.state[IDX_POS_X:IDX_POS_Z+1]
    quat = quad.state[IDX_QUAT_W:IDX_QUAT_Z+1]
    rot = scipy.spatial.transform.Rotation.from_quat(quat, scalar_first=True).as_matrix()
    wHb = np.r_[np.c_[rot,origin], np.array([[0, 0, 0, 1]])]
    quadBodyFrame = quad.body_frame.T
    quadWorldFrame = wHb.dot(quadBodyFrame)
    pos_full_quad = quadWorldFrame[0:3]
    return pos_full_quad

# Function to control the propellers
def control_propellers(quad):
    t = quad.time
    T = 1.5
    r = 2*np.pi * t / T
    prop_thrusts = quad.control(p_d_I = np.array([np.cos(r/2), np.sin(r), 0.0]))
    # prop_thrusts = quad.control(p_d_I = np.array([1, 0, 1]))
    # Note: for Hover mode, just replace the desired trajectory with [1, 0, 1]
    # prop_thrusts = np.array([55, 50, 50, 50])
    # thrust = 50
    # prop_thrusts = np.array([thrust, thrust, thrust, thrust])
    # period = 0.5
    # prop_thrusts[int((t // period) % 4)] = thrust + 1
    # print(prop_thrusts)

    # quad.update(prop_thrusts, dt)
    quad.update_wind(prop_thrusts, dt)

# Main function to run the simulation
def main():
    quadcopter = Robot()
    def control_loop(i):
        for _ in range(PLAYBACK_SPEED):
            control_propellers(quadcopter)
        return get_pos_full_quadcopter(quadcopter)

    plotter = QuadPlotter()
    plotter.plot_animation(control_loop)

# Main function to run the simulation and save the trajectory
# def main():
#     quadcopter = Robot()
#     trajectory = []

#     simulation_time = 10
#     for _ in range(int(simulation_time / dt)):
#         control_propellers(quadcopter)
#         pos_full_quad = get_pos_full_quadcopter(quadcopter)
#         trajectory.append(pos_full_quad)

#     trajectory = np.array(trajectory)
#     np.save("trajectory.npy", trajectory)

#     import matplotlib.pyplot as plt

#     trajectory = np.load("trajectory.npy")

#     fig = plt.figure()
#     ax = fig.add_subplot(111, projection='3d')
#     ax.plot(trajectory[:, 0, 4], trajectory[:, 1, 4], trajectory[:, 2, 4], label='Quadcopter Path')
#     ax.set_xlabel('X')
#     ax.set_ylabel('Y')
#     ax.set_zlabel('Z')
#     ax.legend()
#     plt.show()

def generate_training_data():
    wind_forces = np.arange(0, 3, 1)
    angular_velocities = np.arange(0.5, 2, 0.5) * 2 * np.pi
    for wind in wind_forces:
        for angular_velocity in angular_velocities:
            quadcopter = Robot()
            quadcopter.F0 = np.array([wind, 0.0, 0.0])
            quadcopter.omega_w = angular_velocity
            trajectory = []
            data = []
            simulation_time = 125
            for _ in range(int(simulation_time / dt)):
                control_propellers(quadcopter)
                state = quadcopter.state
                omega_motor = quadcopter.omega_motors
                trajectory.append(get_pos_full_quadcopter(quadcopter))
                data.append(np.concatenate([state[IDX_VEL_X:IDX_VEL_Z+1], state[IDX_QUAT_W:IDX_QUAT_Z+1], omega_motor, quadcopter.wind_force]))

            data = np.array(data)
            np.save(f"data/data_wind_{wind}_omega_{angular_velocity}.npy", data)
            trajectory = np.array(trajectory)
            np.save(f"data/trajectory_wind_{wind}_omega_{angular_velocity}.npy", trajectory)

            import matplotlib.pyplot as plt

            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')
            ax.plot(trajectory[:, 0, 4], trajectory[:, 1, 4], trajectory[:, 2, 4], label=f'Wind {wind}, Omega {angular_velocity}')
            ax.set_xlabel('X')
            ax.set_ylabel('Y')
            ax.set_zlabel('Z')
            ax.legend()
            plt.savefig(f"data/trajectory_wind_{wind}_omega_{angular_velocity}.png")
            plt.close()

            plt.figure()
            plt.plot(np.arange(0, simulation_time, dt), data[:, -3], label='Wind Force X')
            plt.plot(np.arange(0, simulation_time, dt), data[:, -2], label='Wind Force Y')
            plt.plot(np.arange(0, simulation_time, dt), data[:, -1], label='Wind Force Z')
            plt.xlabel('Time [s]')
            plt.ylabel('Wind Force [N]')
            plt.legend()
            plt.savefig(f"data/wind_force_wind_{wind}_omega_{angular_velocity}.png")
            plt.close()

if __name__ == "__main__":
    generate_training_data()
