"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

const PARTICLE_COUNT = 360;
const SPHERE_RADIUS = 2.35;

function buildSpherePositions() {
  const positions: number[] = [];
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));

  for (let index = 0; index < PARTICLE_COUNT; index += 1) {
    const y = 1 - (index / (PARTICLE_COUNT - 1)) * 2;
    const radius = Math.sqrt(1 - y * y);
    const theta = goldenAngle * index;
    const jitter = 0.94 + ((index * 17) % 23) / 260;

    positions.push(
      Math.cos(theta) * radius * SPHERE_RADIUS * jitter,
      y * SPHERE_RADIUS * jitter,
      Math.sin(theta) * radius * SPHERE_RADIUS * jitter
    );
  }

  return positions;
}

function buildLinePositions(points: number[]) {
  const lines: number[] = [];
  const maxConnections = 520;

  for (
    let i = 0;
    i < PARTICLE_COUNT && lines.length / 6 < maxConnections;
    i += 1
  ) {
    const ix = points[i * 3];
    const iy = points[i * 3 + 1];
    const iz = points[i * 3 + 2];

    for (
      let j = i + 1;
      j < PARTICLE_COUNT && lines.length / 6 < maxConnections;
      j += 1
    ) {
      if ((i + j) % 11 !== 0) {
        continue;
      }

      const jx = points[j * 3];
      const jy = points[j * 3 + 1];
      const jz = points[j * 3 + 2];
      const distance = Math.hypot(ix - jx, iy - jy, iz - jz);

      if (distance < 0.76) {
        lines.push(ix, iy, iz, jx, jy, jz);
      }
    }
  }

  return lines;
}

export function NeuralSphere() {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    camera.position.set(0, 0, 7);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);

    const pointPositions = buildSpherePositions();
    const pointGeometry = new THREE.BufferGeometry();
    pointGeometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(pointPositions, 3)
    );

    const pointMaterial = new THREE.PointsMaterial({
      color: "#67e8b9",
      size: 0.028,
      transparent: true,
      opacity: 0.92,
      depthWrite: false
    });
    const points = new THREE.Points(pointGeometry, pointMaterial);
    group.add(points);

    const lineGeometry = new THREE.BufferGeometry();
    lineGeometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(buildLinePositions(pointPositions), 3)
    );
    const lineMaterial = new THREE.LineBasicMaterial({
      color: "#8cc8ff",
      transparent: true,
      opacity: 0.24,
      depthWrite: false
    });
    const lines = new THREE.LineSegments(lineGeometry, lineMaterial);
    group.add(lines);

    const innerGeometry = new THREE.SphereGeometry(1.18, 48, 32);
    const innerMaterial = new THREE.MeshBasicMaterial({
      color: "#67e8b9",
      transparent: true,
      opacity: 0.035,
      wireframe: true
    });
    const innerSphere = new THREE.Mesh(innerGeometry, innerMaterial);
    group.add(innerSphere);

    const pointer = new THREE.Vector2(0, 0);
    const target = new THREE.Vector2(0, 0);

    const handlePointerMove = (event: PointerEvent) => {
      const rect = container.getBoundingClientRect();
      target.x = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
      target.y = ((event.clientY - rect.top) / rect.height - 0.5) * 2;
    };

    const resize = () => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      camera.aspect = width / Math.max(height, 1);
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    };

    let frameId = 0;
    const clock = new THREE.Clock();

    const animate = () => {
      const elapsed = clock.getElapsedTime();
      pointer.lerp(target, 0.045);

      group.rotation.y = elapsed * 0.12 + pointer.x * 0.34;
      group.rotation.x = Math.sin(elapsed * 0.28) * 0.12 + pointer.y * 0.22;
      group.rotation.z = Math.cos(elapsed * 0.18) * 0.05;
      camera.position.x = pointer.x * 0.16;
      camera.position.y = -pointer.y * 0.12;
      camera.lookAt(0, 0, 0);

      renderer.render(scene, camera);
      frameId = window.requestAnimationFrame(animate);
    };

    resize();
    animate();

    window.addEventListener("resize", resize);
    container.addEventListener("pointermove", handlePointerMove);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("resize", resize);
      container.removeEventListener("pointermove", handlePointerMove);
      pointGeometry.dispose();
      pointMaterial.dispose();
      lineGeometry.dispose();
      lineMaterial.dispose();
      innerGeometry.dispose();
      innerMaterial.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return (
    <div
      ref={containerRef}
      aria-hidden="true"
      className="h-[360px] w-full sm:h-[460px] lg:h-[620px]"
    />
  );
}
