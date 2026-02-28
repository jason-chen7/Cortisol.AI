/**
 * Head3D.jsx
 * Three.js rotating stylised face.
 * - Continuously rotates on Y axis
 * - Mouth opens proportionally to mic amplitude (RMS)
 * - Rim light + scene background smoothly interpolate to the current stress color
 */

import { useEffect, useRef } from 'react'
import * as THREE from 'three'

// ── Stress palette ────────────────────────────────────────────────────────────
const PALETTE = {
  green:  { bg: 0x011a10, rim: 0x22c55e, rimIntensity: 3.0 },
  yellow: { bg: 0x1a1000, rim: 0xeab308, rimIntensity: 3.0 },
  red:    { bg: 0x1a0404, rim: 0xef4444, rimIntensity: 3.5 },
}

export default function Head3D({ analyserNode, stressColor = 'green', frozen = false }) {
  const mountRef    = useRef(null)
  const colorRef    = useRef(stressColor)
  const analyserRef = useRef(analyserNode)
  const frozenRef   = useRef(frozen)

  // Keep refs in sync with props (no scene rebuild needed)
  useEffect(() => { colorRef.current = stressColor },    [stressColor])
  useEffect(() => { analyserRef.current = analyserNode }, [analyserNode])
  useEffect(() => { frozenRef.current = frozen },        [frozen])

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    // ── Renderer ──────────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(mount.clientWidth, mount.clientHeight)
    renderer.shadowMap.enabled = true
    mount.appendChild(renderer.domElement)

    // ── Scene / camera ────────────────────────────────────────────────────────
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(PALETTE.green.bg)

    const camera = new THREE.PerspectiveCamera(
      52,
      mount.clientWidth / mount.clientHeight,
      0.1,
      60,
    )
    camera.position.set(0, 0.15, 4.8)

    // ── Lights ────────────────────────────────────────────────────────────────
    const ambient = new THREE.AmbientLight(0xffffff, 0.45)
    scene.add(ambient)

    const keyLight = new THREE.DirectionalLight(0xfff5e8, 1.4)
    keyLight.position.set(3, 5, 6)
    scene.add(keyLight)

    const rimLight = new THREE.PointLight(PALETTE.green.rim, PALETTE.green.rimIntensity, 14)
    rimLight.position.set(-3.5, 1, -3)
    scene.add(rimLight)

    const topLight = new THREE.PointLight(0x8899ff, 0.5, 10)
    topLight.position.set(0, 5, 2)
    scene.add(topLight)

    // ── Materials ─────────────────────────────────────────────────────────────
    const skinMat = new THREE.MeshStandardMaterial({
      color: 0xf0c4a0,
      roughness: 0.72,
      metalness: 0.04,
    })
    const darkMat = new THREE.MeshStandardMaterial({ color: 0x151520, roughness: 0.5 })
    const irisMat = new THREE.MeshStandardMaterial({ color: 0x3b2e6e, roughness: 0.4 })
    const scleraMat = new THREE.MeshStandardMaterial({
      color: 0xf8f8f8,
      roughness: 0.3,
      emissive: 0x111111,
    })
    const shineMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      emissive: 0xffffff,
      emissiveIntensity: 0.9,
      roughness: 0.1,
    })
    const lipMat = new THREE.MeshStandardMaterial({ color: 0xb5606e, roughness: 0.55 })
    const mouthInteriorMat = new THREE.MeshStandardMaterial({ color: 0x150505 })

    // ── Head group ────────────────────────────────────────────────────────────
    const headGroup = new THREE.Group()
    scene.add(headGroup)

    // Skull — slightly tall, slightly shallow on Z for a face shape
    const skull = new THREE.Mesh(new THREE.SphereGeometry(1.2, 64, 64), skinMat)
    skull.scale.set(1.0, 1.18, 0.92)
    headGroup.add(skull)

    // Neck stump
    const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.38, 0.42, 0.55, 24), skinMat)
    neck.position.set(0, -1.28, 0)
    headGroup.add(neck)

    // Ears
    ;[-1, 1].forEach((side) => {
      const ear = new THREE.Mesh(new THREE.SphereGeometry(0.27, 20, 20), skinMat)
      ear.scale.set(0.38, 0.7, 0.32)
      ear.position.set(side * 1.19, 0.1, 0.0)
      headGroup.add(ear)
    })

    // ── Eyes ──────────────────────────────────────────────────────────────────
    ;[
      [-0.4, 0.3, 1.0],
      [ 0.4, 0.3, 1.0],
    ].forEach(([x, y, z]) => {
      // Sclera
      const sclera = new THREE.Mesh(new THREE.SphereGeometry(0.165, 24, 24), scleraMat)
      sclera.scale.set(1, 0.95, 0.65)
      sclera.position.set(x, y, z)
      headGroup.add(sclera)

      // Iris
      const iris = new THREE.Mesh(new THREE.SphereGeometry(0.1, 20, 20), irisMat)
      iris.position.set(x, y, z + 0.09)
      headGroup.add(iris)

      // Pupil
      const pupil = new THREE.Mesh(new THREE.SphereGeometry(0.056, 16, 16), darkMat)
      pupil.position.set(x, y, z + 0.155)
      headGroup.add(pupil)

      // Highlight
      const shine = new THREE.Mesh(new THREE.SphereGeometry(0.028, 10, 10), shineMat)
      shine.position.set(x + 0.04, y + 0.04, z + 0.18)
      headGroup.add(shine)
    })

    // Eyebrows
    ;[-0.4, 0.4].forEach((x) => {
      const brow = new THREE.Mesh(
        new THREE.BoxGeometry(0.34, 0.055, 0.05),
        new THREE.MeshStandardMaterial({ color: 0x6b3a2a, roughness: 0.8 }),
      )
      brow.position.set(x, 0.54, 1.06)
      brow.rotation.z = x < 0 ? 0.12 : -0.12
      headGroup.add(brow)
    })

    // ── Nose ──────────────────────────────────────────────────────────────────
    const noseBase = new THREE.Mesh(new THREE.SphereGeometry(0.1, 20, 20), skinMat)
    noseBase.scale.set(1.1, 0.75, 1.3)
    noseBase.position.set(0, -0.04, 1.16)
    headGroup.add(noseBase)

    // Nostrils
    ;[-0.07, 0.07].forEach((x) => {
      const nostril = new THREE.Mesh(new THREE.SphereGeometry(0.055, 14, 14), skinMat)
      nostril.scale.set(0.9, 0.7, 0.7)
      nostril.position.set(x, -0.09, 1.13)
      headGroup.add(nostril)
    })

    // ── Mouth ─────────────────────────────────────────────────────────────────
    const mouthPivot = new THREE.Group()
    mouthPivot.position.set(0, -0.44, 1.08)   // pushed forward past face surface
    headGroup.add(mouthPivot)

    const upperLip = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.09, 0.1), lipMat)
    upperLip.position.set(0, 0.052, 0)
    mouthPivot.add(upperLip)

    const lowerLip = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.10, 0.1), lipMat)
    lowerLip.position.set(0, -0.052, 0)
    mouthPivot.add(lowerLip)

    // Dark interior — scales on Y when mouth opens
    const mouthInner = new THREE.Mesh(new THREE.BoxGeometry(0.54, 0.01, 0.08), mouthInteriorMat)
    mouthInner.position.set(0, 0, -0.02)
    mouthPivot.add(mouthInner)

    // ── Glow halo (stress color aura) ─────────────────────────────────────────
    const haloMat = new THREE.MeshBasicMaterial({
      color: PALETTE.green.rim,
      transparent: true,
      opacity: 0.055,
      side: THREE.BackSide,
    })
    const halo = new THREE.Mesh(new THREE.SphereGeometry(1.7, 32, 32), haloMat)
    headGroup.add(halo)

    // ── Color interpolation state ─────────────────────────────────────────────
    const currentBg  = new THREE.Color(PALETTE.green.bg)
    const targetBg   = new THREE.Color(PALETTE.green.bg)
    const currentRim = new THREE.Color(PALETTE.green.rim)
    const targetRim  = new THREE.Color(PALETTE.green.rim)

    // ── Audio state ───────────────────────────────────────────────────────────
    let pcmData = null

    // ── Animation loop ────────────────────────────────────────────────────────
    let rafId
    const clock = new THREE.Clock()

    function animate() {
      rafId = requestAnimationFrame(animate)
      const t = clock.getElapsedTime()

      // Rotate when idle/recording; smoothly face forward when speaking
      if (frozenRef.current) {
        headGroup.rotation.y += (0 - headGroup.rotation.y) * 0.06
      } else {
        headGroup.rotation.y = t * 0.55
      }

      // Subtle vertical bob
      headGroup.position.y = Math.sin(t * 0.9) * 0.07

      // ── Stress color transitions ───────────────────────────────────────────
      const pal = PALETTE[colorRef.current] ?? PALETTE.green
      targetBg.setHex(pal.bg)
      targetRim.setHex(pal.rim)
      currentBg.lerp(targetBg, 0.04)
      currentRim.lerp(targetRim, 0.06)

      scene.background.copy(currentBg)
      rimLight.color.copy(currentRim)
      rimLight.intensity = pal.rimIntensity
      haloMat.color.copy(currentRim)

      // ── Mouth open from audio amplitude ───────────────────────────────────
      const analyser = analyserRef.current
      let open = 0

      if (analyser) {
        if (!pcmData || pcmData.length !== analyser.frequencyBinCount) {
          pcmData = new Uint8Array(analyser.frequencyBinCount)
        }
        analyser.getByteTimeDomainData(pcmData)

        // RMS amplitude
        let sum = 0
        for (let i = 0; i < pcmData.length; i++) {
          const v = (pcmData[i] - 128) / 128.0
          sum += v * v
        }
        open = Math.min(Math.sqrt(sum / pcmData.length) * 5.5, 0.25)
      }

      // Smooth lip positions toward target
      const targetLower = -0.048 - open
      const targetUpper =  0.048 + open * 0.28
      lowerLip.position.y += (targetLower - lowerLip.position.y) * 0.25
      upperLip.position.y += (targetUpper - upperLip.position.y) * 0.25
      mouthInner.scale.y = Math.max(1, open * 28)

      renderer.render(scene, camera)
    }

    animate()

    // ── Resize ────────────────────────────────────────────────────────────────
    const onResize = () => {
      const w = mount.clientWidth
      const h = mount.clientHeight
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    window.addEventListener('resize', onResize)

    return () => {
      cancelAnimationFrame(rafId)
      window.removeEventListener('resize', onResize)
      renderer.dispose()
      if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement)
    }
  }, []) // scene is built once; color + analyser update via refs

  return <div ref={mountRef} style={{ width: '100%', height: '100%' }} />
}
