import sys
import pwd
import usb.core
import usb.util
import os
import json
import subprocess

VENDOR_ID=0X046d
PRODUCT_ID=0Xc214
PROFILE_BASE="/usr/share/atk3profiles"

class ATK3Base:
    
    def __init__(self, vendor=0x046d, product=0xc214):
        self.v = vendor
        self.p = product

    def parse(self, x):
        out = {
            "roll": x[0],
            "pitch": x[1],
            "dial": x[2],
            "key0": x[3],
            "key1": x[4],
            "keyhash": f"{x[3]}:{x[4]}"
        }
        return out

    def read(self):
        dev = usb.core.find(idVendor=self.v, idProduct=self.p)
        interface = 0
        endpoint = dev[0][(0,0)][0]
        if dev.is_kernel_driver_active(interface) is True:
          dev.detach_kernel_driver(interface)
          usb.util.claim_interface(dev, interface)
        while True:
            try:
                data = dev.read(endpoint.bEndpointAddress,endpoint.wMaxPacketSize)
                yield self.parse(data)
            except usb.core.USBError as e:
                if e.args == ('Operation timed out',):
                    continue

class ATK3InteractiveMapper(ATK3Base):

    def __init__(self, *args):
        super().__init__()
        self.mapset = {}

    def map(self):
        self.save_profile(self.read_and_map())

    def read_and_map(self):
        profile = {}
        for inp in self.read():
            if inp['keyhash'] in profile:
                continue
            else:
                print("="*10)
                print(f"unique keyhash: {inp['keyhash']}")
                conf = False
                while not conf:
                    desc = input("desc: ")
                    cmd = input("cmd: ")
                    print(f"{inp['keyhash']} ==> {desc}, {cmd}")
                    conf = input("y/n? ").lower() == "y"
                profile[inp['keyhash']] = [desc, cmd]
                if input("done? (y/n) ").lower() == "y":
                    break
                print()
        return profile

    def save_profile(self, profile):
        name = input("profile name: ")
        os.makedirs(PROFILE_BASE, exist_ok=True)
        fname = os.path.join(PROFILE_BASE, name + ".json")
        with open(fname, "w") as fp:
            fp.write(json.dumps(profile))

class ATK3Launcher(ATK3Base):

    def __init__(self, profile, **kw):
        super().__init__()
        self.profile_path = os.path.join(PROFILE_BASE, profile + ".json")
        self.profile = json.loads(open(self.profile_path, "r").read())

    def demote(self, user_uid, user_gid):
        def result():
            os.setgid(user_gid)
            os.setuid(user_uid)
        return result

    def build_user_env(self):
        pw_record = pwd.getpwnam("skilleduser")
        user_name      = pw_record.pw_name
        user_home_dir  = pw_record.pw_dir
        user_uid       = pw_record.pw_uid
        user_gid       = pw_record.pw_gid
        env = os.environ.copy()
        env[ 'HOME'     ]  = user_home_dir
        env[ 'LOGNAME'  ]  = user_name
        env[ 'PWD'      ]  = "/home/skilleduser"
        env[ 'USER'     ]  = user_name
        return env, self.demote(user_uid, user_gid)

    def read_and_launch(self):
        print(self.profile)
        for inp in self.read():
            keyhash = inp["keyhash"]
            launch = self.profile.get(keyhash, None)
            if launch is None:
                continue
            description, command = launch
            print(keyhash, launch)
            env, pre= self.build_user_env()
            subprocess.Popen(
                command.split(" "), 
                preexec_fn=pre,
                env=env,
            )

if __name__ == "__main__":
    import signal
    import sys
    import argparse

    def sigint_handler(*args):
        print("\nATK3 done")
        sys.exit(0)

    signal.signal(signal.SIGINT, sigint_handler)

    parser = argparse.ArgumentParser()
    parser.add_argument("-m", default="launch", type=str, help="ATK3 mode {launch, map}")
    parser.add_argument("-p", default="sample1", type=str, help="ATK3 launch profile")
    args = parser.parse_args()

    if args.m == "launch":
        print("ATK3: launch mode with profile {}...".format(args.p))
        driver = ATK3Launcher(args.p)
        driver.read_and_launch()
    elif args.m == "map":
        print("ATK3: map mode...")
        mapper = ATK3InteractiveMapper()
        mapper.map()
    else:
        print("ATK3: invalid mode")
        sys.exit(1)
