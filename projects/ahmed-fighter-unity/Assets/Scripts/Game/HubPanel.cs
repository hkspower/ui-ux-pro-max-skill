using UnityEngine;
using Ahmed.Combat;
using Ahmed.Data;
using Ahmed.World;

namespace Ahmed.Game
{
    /// <summary>
    /// The upgrade base, drawn while Ahmed stands in the hub.
    ///
    /// This is the port's only interface, and it is IMGUI on purpose: the
    /// project has no authored scene, so a Canvas would mean an asset, a font
    /// and a prefab, none of which can be made without an editor. OnGUI needs
    /// none of them and draws from code, the same bargain Bootstrap makes for
    /// everything else. It is a placeholder for a real HUD, not an argument
    /// against one.
    ///
    /// Every decision it can make lives in <see cref="UpgradeStore"/>, which
    /// is pure and executed under test. This class is the keys and the labels.
    /// </summary>
    public class HubPanel : MonoBehaviour
    {
        private static readonly KeyCode[] Keys =
        {
            KeyCode.Alpha1, KeyCode.Alpha2, KeyCode.Alpha3, KeyCode.Alpha4, KeyCode.Alpha5
        };

        private DistrictRuntime _world;

        private void Start() { _world = DistrictRuntime.Current; }

        private void Update()
        {
            if (_world == null) { _world = DistrictRuntime.Current; }
            if (_world == null || !_world.InHub) { return; }

            for (int i = 0; i < Keys.Length && i < TrackCount; i++)
            {
                if (!Input.GetKeyDown(Keys[i])) { continue; }
                Buy((UpgradeTrack)i);
            }
        }

        private static int TrackCount
        {
            get { return System.Enum.GetValues(typeof(UpgradeTrack)).Length; }
        }

        private void Buy(UpgradeTrack track)
        {
            if (!UpgradeStore.Buy(track))
            {
                AudioLibrary.PlayUI("UI_Denied");
                return;
            }
            PlayerFighter player = PlayerFighter.Current;
            if (player != null) { player.ApplyUpgrades(); }
            // Bought at a save point, so the purchase is banked with it. A
            // player who buys and quits must not lose the level.
            SaveGame.Write();
            AudioLibrary.PlayUI("Upgrade_Bought");
        }

        private void OnGUI()
        {
            if (_world == null || !_world.InHub) { return; }

            const float w = 460f, rowH = 26f;
            float h = 76f + TrackCount * rowH;
            Rect box = new Rect(20f, 20f, w, h);
            GUI.Box(box, "");

            GUI.Label(new Rect(box.x + 14f, box.y + 10f, w - 28f, 22f),
                "SAVE POINT — saved. " + WorldState.Experience + " XP unspent.");
            GUI.Label(new Rect(box.x + 14f, box.y + 32f, w - 28f, 22f),
                "Press a number to train:");

            for (int i = 0; i < TrackCount; i++)
            {
                UpgradeTrack track = (UpgradeTrack)i;
                UpgradeRow info = GameData.UpgradeInfo(track);
                int level = WorldState.UpgradeLevel(track);
                int cost = UpgradeStore.NextCost(track);
                string price = cost < 0 ? "MAX" : cost + " XP";

                GUI.color = cost < 0 || UpgradeStore.CanAfford(track) ? Color.white : Color.gray;
                GUI.Label(new Rect(box.x + 14f, box.y + 58f + i * rowH, w - 28f, rowH),
                    (i + 1) + "  " + (info != null ? info.displayName : track.ToString())
                    + "   " + level + "/" + UpgradeStore.MaxLevel + "   " + price
                    + "   " + (info != null ? info.description : ""));
            }
            GUI.color = Color.white;
        }
    }
}
