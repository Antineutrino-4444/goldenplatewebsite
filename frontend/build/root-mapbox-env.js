import { loadEnv } from 'vite'

export default function rootMapboxEnv(directory) {
  return {
    name: 'root-mapbox-env',
    config(_config, { mode }) {
      // Read only the public map token; keep backend secrets out of the bundle
      // and preserve the frontend's existing environment files for Turnstile.
      const token = loadEnv(mode, directory, 'VITE_MAPBOX_ACCESS_TOKEN').VITE_MAPBOX_ACCESS_TOKEN
      if (token === undefined) return
      return {
        define: { 'import.meta.env.VITE_MAPBOX_ACCESS_TOKEN': JSON.stringify(token) },
      }
    },
  }
}
